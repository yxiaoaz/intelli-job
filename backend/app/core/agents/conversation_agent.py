from deepagents import create_deep_agent, FilesystemMiddleware
from deepagents.backends import CompositeBackend, FilesystemBackend
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy import select
from app.core.backends.db_backend import DbBackend
from app.services.llm_service import LLMService, extract_prompt_cache_usage
from app.services.job_matching_service import JobMatchingService
from app.services.query_formulator import QueryFormulator
from app.services.query_enhancer import extract_resume_profile
from app.services.intent_file_service import IntentFileService
from app.repositories.user_repo import UserRepository
from app.repositories.job_repo import BookmarkRepository, JobRepository
from app.memory.service import MemoryService
from app.memory.schemas import SessionMemory, UserMemory, JobPreference
from app.config import get_settings
from app.core.checkpointer_factory import get_checkpointer
from app.models import Resume
from app.database import AsyncSessionLocal
from app.utils.logger import get_logger
import uuid
import json

logger = get_logger()

# ✅ 招聘类型中文 → 枚举值映射：agent 常直接传"实习"等中文，
# 透传会被 JobPreference 的 Literal 校验拒绝（工具报错 → 复读追问）
_RECRUITMENT_TYPE_ALIASES = {
    "实习": "INTERN", "实习生": "INTERN", "intern": "INTERN", "internship": "INTERN",
    "校招": "GRADUATE", "应届": "GRADUATE", "应届生": "GRADUATE",
    "校园招聘": "GRADUATE", "graduate": "GRADUATE",
    "社招": "EXPERIENCED", "社会招聘": "EXPERIENCED", "experienced": "EXPERIENCED",
}


def _normalize_preference_updates(updates: dict) -> tuple[dict, list[str]]:
    """归一化 update_session_memory 的偏好字段，返回 (normalized, dropped_fields)。

    - recruitment_types：中文/大小写归一到合法枚举；全部无法识别时丢弃该字段
    - locations：去掉"市"后缀（如 "北京市" → "北京"），与库内城市名对齐
    """
    dropped: list[str] = []
    prefs = updates.get("preferences")
    if not isinstance(prefs, dict):
        return updates, dropped
    prefs = dict(prefs)

    if "recruitment_types" in prefs:
        raw = prefs["recruitment_types"]
        if isinstance(raw, list):
            normalized = []
            for item in raw:
                if not isinstance(item, str):
                    continue
                key = item.strip()
                mapped = _RECRUITMENT_TYPE_ALIASES.get(key) or _RECRUITMENT_TYPE_ALIASES.get(key.lower())
                if mapped:
                    normalized.append(mapped)
            if normalized:
                prefs["recruitment_types"] = sorted(set(normalized))
            else:
                prefs.pop("recruitment_types")
                dropped.append("preferences.recruitment_types")

    if isinstance(prefs.get("locations"), list):
        prefs["locations"] = [
            loc.rstrip("市") if isinstance(loc, str) and len(loc) > 2 else loc
            for loc in prefs["locations"]
        ]

    return {**updates, "preferences": prefs}, dropped


def _log_prompt_cache_usage(session_id: str, usages: list[dict]) -> None:
    """输出本轮 prompt cache 命中汇总（Phase 5.1）。

    一行一轮而不是一次调用一行：验收要看的是“hit 随轮次单调增长”，
    单轮内有多次模型调用（工具循环），汇总后的曲线才可读；细节放在 per_call 里。
    拿不到 usage 时也要 log（记 0 调用），否则“没数据”与“没埋点”分不清。
    """
    logger.info(
        "llm_prompt_cache_usage",
        session_id=session_id,
        model_calls=len(usages),
        hit_tokens=sum(int(u.get("hit") or 0) for u in usages),
        miss_tokens=sum(int(u.get("miss") or 0) for u in usages),
        input_tokens=sum(int(u.get("input_tokens") or 0) for u in usages),
        per_call=[[u.get("hit"), u.get("miss")] for u in usages],
    )


class ConversationAgent:
    """DeepAgent for conversational job assistance using deepagents framework"""

    def __init__(self):
        self.llm_service = LLMService()
        self.job_matching_service = JobMatchingService()
        self.intent_file_service = IntentFileService()
        # Agent 将在每次 chat 调用时动态创建，以支持 session 隔离
        # ✅ 流式 token 过滤：deepagents/langgraph 链路下，多供应商
        # FallbackChatModel 的每个 token 会双发 on_chat_model_stream
        # （内层 name=ChatOpenAI / 外层 name=FallbackChatModel，run_id 相同），
        # 且 QueryFormulator 等内部 LLM 调用的流式 token 也会混入。
        # 只接受外层来源的事件即可同时去重和阻断内部流泄露。
        self._stream_source_name = type(self.llm_service.chat_model).__name__

    def _create_agent(self, session_id: str, user_id: str | None = None, checkpointer=None):
        """Create the Deep Agent using deepagents.create_deep_agent

        Args:
            session_id: Session ID for file system isolation
            user_id: User ID (optional)
            checkpointer: Optional LangGraph checkpointer for persistence
        """

        # Define tools
        @tool
        async def search_jobs(
            query: str,
            filters: dict | None = None,
        ) -> str:
            """Search for matching jobs based on query and filters.

            后端会自动加载 SessionMemory / UserMemory / active_resume，
            并通过 QueryFormulator 生成 JD 视角的检索 query。

            Args:
                query: 目标岗位关键词（1-3 个词，仅填岗位名称）
                    示例: "产品经理"、"Java后端"、"数据分析"
                    不要加城市/薪资/经验等信息（走 preferences）
                filters: Optional hard filters (recruitment_type, education_level, etc.)

            Returns:
                JSON 格式的岗位搜索结果

            注：用户与会话身份由工具闭包持有（见 Phase 4.3），**不能从参数传入**——
            以前形参可以被模型随意填，既有越权风险也会因为漏传而丢失个性化。
            """
            if filters is None:
                filters = {}
            try:
                logger.info(
                    "search_jobs_tool_called",
                    query=query,
                    filters=filters,
                    session_id=session_id,
                    user_id=user_id
                )

                # ── 加载记忆 + 简历 ──────────────────────────────
                session_preferences = JobPreference()
                user_memory = None
                resume_profile = {}
                resume_id = None

                if user_id:
                    try:
                        async with AsyncSessionLocal() as mem_db:
                            memory_service = MemoryService(
                                db=mem_db,
                                base_dir=self.intent_file_service.base_dir,
                            )
                            # SessionMemory
                            if session_id:
                                session_mem = await memory_service.get_or_init_session_memory(
                                    uuid.UUID(user_id), session_id
                                )
                                session_preferences = session_mem.preferences
                            # UserMemory
                            user_memory = await memory_service.get_user_memory(uuid.UUID(user_id))
                    except Exception as e:
                        logger.warning("search_jobs_memory_load_failed", error=str(e))

                    # active_resume
                    try:
                        async with AsyncSessionLocal() as resume_db:
                            result = await resume_db.execute(
                                select(Resume).where(
                                    Resume.user_id == uuid.UUID(user_id),
                                    Resume.active_status == True
                                ).limit(1)
                            )
                            active_resume = result.scalar_one_or_none()
                            if active_resume and active_resume.extracted_content:
                                resume_profile = extract_resume_profile(active_resume.extracted_content)
                                resume_id = str(active_resume.id)
                    except Exception as e:
                        logger.warning("search_jobs_resume_load_failed", error=str(e))

                # ── QueryFormulator ──────────────────────────────
                formulator = QueryFormulator()
                formulated = await formulator.formulate(
                    natural_query=query,
                    session_preferences=session_preferences,
                    user_memory=user_memory,
                    resume_profile=resume_profile,
                    resume_id=resume_id,
                    hard_filters=filters,
                )
                expanded_query = formulated["expanded_query"]

                logger.info(
                    "query_formulated",
                    original=query,
                    expanded=expanded_query[:100],
                    synonyms=formulated.get("synonyms", []),
                )

                # ── match_jobs ───────────────────────────────────
                async with AsyncSessionLocal() as db_session:
                    job_repo = JobRepository(db_session)

                    results = await self.job_matching_service.match_jobs(
                        user_query_preference={"keywords": expanded_query},
                        user_resume_profile={},  # 简历已融入 query，不再二次注入
                        hard_filters=filters,
                        top_k=10,
                        job_repo=job_repo,
                        skip_enhancement=True,  # QueryFormulator 已做增强
                    )

                logger.info(
                    "search_jobs_tool_completed",
                    result_count=len(results) if results else 0
                )

                if not results:
                    return "没有找到匹配的职位"

                # ── 构造结构化 JSON 数据（供前端解析）────────────
                # 无简历时不给假分数：旧逻辑无简历时 score 兜底到 ~1%，
                # agent 会照着念"匹配度 1%"打击信心，与前端"—"展示也不同步
                has_resume = bool(resume_profile)
                jobs_data = []
                for item in results[:5]:  # Top 5 results
                    job = item["job_item"]
                    score = item.get("score", 0)
                    full_desc = job.description or ""

                    jobs_data.append({
                        "id": str(job.id),
                        "title": job.job_title,
                        "company": job.company_name,
                        "location": job.location,
                        "salary_min": None,
                        "salary_max": None,
                        "salary": job.salary,
                        "salary_currency": "CNY",
                        "description": full_desc,
                        "truncated_description": full_desc[:150] + "..." if len(full_desc) > 150 else full_desc,
                        "requirements": [],
                        "url": job.url,
                        "source": job.source.value if hasattr(job.source, 'value') else str(job.source),
                        "match_score": round(score * 100, 1) if has_resume else None,
                        "match_analysis": (
                            f"匹配度 {score:.1%}" if has_resume
                            else "暂无简历，无法评估匹配度"
                        ),
                        # 补全字段
                        "update_time": job.update_time.isoformat() if job.update_time else None,
                        "recruitment_type": job.recruitment_type.value if job.recruitment_type else None,
                        "education": job.min_academic_qualification.value if job.min_academic_qualification else None,
                        "skills": [],
                    })

                return json.dumps({
                    "type": "job_search_results",
                    "count": len(jobs_data),
                    "jobs": jobs_data
                }, ensure_ascii=False)
            except Exception as e:
                logger.error("search_jobs_tool_failed", error=str(e))
                return f"搜索失败: {str(e)}"

        @tool
        async def get_user_profile() -> str:
            """Get current user's profile summary including skills and preferences.

            用户身份由工具闭包持有，无需传参（传 user_id 会被模型编造，越权风险）。

            Returns:
                Formatted user profile information
            """
            if not user_id:
                return "未识别当前用户，无法读取档案"
            try:
                logger.info(
                    "get_user_profile_tool_called",
                    user_id=user_id
                )

                async with AsyncSessionLocal() as db_session:
                    user_repo = UserRepository(db_session)
                    user = await user_repo.get_by_id(uuid.UUID(user_id))

                    if not user:
                        return f"用户 {user_id} 不存在"

                    # Get active resume if exists
                    profile_info = [f"用户名: {user.username}"]

                    # Check for active resume
                    from app.models import Resume
                    result = await db_session.execute(
                        select(Resume).where(
                            Resume.user_id == user.id,
                            Resume.active_status == True
                        ).limit(1)
                    )
                    active_resume = result.scalar_one_or_none()

                    if active_resume and active_resume.extracted_content:
                        content = active_resume.extracted_content

                        # Extract key info from parsed resume
                        if content.get("skills"):
                            skills = content["skills"]
                            if isinstance(skills, list):
                                profile_info.append(f"技能: {', '.join(skills[:10])}")
                            elif isinstance(skills, str):
                                profile_info.append(f"技能: {skills}")

                        if content.get("work_experience"):
                            exp_list = content["work_experience"]
                            if isinstance(exp_list, list) and len(exp_list) > 0:
                                latest_exp = exp_list[0]
                                if latest_exp.get("company"):
                                    profile_info.append(f"最近公司: {latest_exp['company']}")
                                if latest_exp.get("title"):
                                    profile_info.append(f"最近职位: {latest_exp['title']}")

                        if content.get("education"):
                            edu_list = content["education"]
                            if isinstance(edu_list, list) and len(edu_list) > 0:
                                latest_edu = edu_list[0]
                                if latest_edu.get("school"):
                                    profile_info.append(f"学校: {latest_edu['school']}")
                                if latest_edu.get("degree"):
                                    profile_info.append(f"学历: {latest_edu['degree']}")
                    else:
                        profile_info.append("暂无简历信息")

                    profile_str = "\n".join(profile_info)

                    logger.info(
                        "get_user_profile_tool_completed",
                        user_id=user_id,
                        has_resume=active_resume is not None
                    )

                    return profile_str
            except Exception as e:
                logger.error("get_user_profile_tool_failed", error=str(e))
                return f"获取用户信息失败: {str(e)}"

        @tool
        async def analyze_job_match(job_description: str, user_skills: str) -> str:
            """Analyze how well a job matches user's skills.

            Args:
                job_description: Full job description
                user_skills: User's skills as comma-separated string

            Returns:
                Structured JSON with match_score, match_reasons, match_risks, resume_tips
            """
            try:
                logger.info(
                    "analyze_job_match_tool_called",
                    job_desc_length=len(job_description),
                    skills=user_skills
                )

                system_prompt = """你是一个专业的求职顾问。请分析以下岗位描述与用户技能的匹配度。

请严格按以下 JSON 格式返回（不要添加任何其他文字、markdown 标记或解释）：
{"match_score": 85, "match_reasons": ["原因1", "原因2"], "match_risks": ["风险1"], "resume_tips": [{"original": "原文", "suggested": "建议改法"}]}

规则：
- match_score: 0-100 的整数
- match_reasons: 2-4 条匹配原因
- match_risks: 1-3 条差距或风险
- resume_tips: 0-3 条简历修改建议，每条包含 original 和 suggested
- 始终使用中文"""

                user_prompt = f"""【用户技能】
{user_skills}

【岗位描述】
{job_description[:2000]}

请分析匹配度并返回 JSON。"""

                logger.info("calling_llm_for_job_match_analysis")
                response = await self.llm_service.generate_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )

                # 解析 JSON（兼容 markdown code block）
                cleaned = response.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

                try:
                    result = json.loads(cleaned)
                    return json.dumps(result, ensure_ascii=False)
                except json.JSONDecodeError:
                    # LLM 未返回有效 JSON，原样返回
                    return response.content if hasattr(response, 'content') else str(response)
            except Exception as e:
                logger.error("analyze_job_match_tool_failed", error=str(e))
                return f"分析失败: {str(e)}"

        # ═══════════════════════════════════════════════════════
        # ✅ 新增工具：update_session_memory（闭包风格）
        # ═══════════════════════════════════════════════════════
        @tool
        async def update_session_memory(updates: dict, mode: str = "merge") -> str:
            """更新当前对话状态（session memory）。

            list 字段（open_questions / recent_decisions）会自动 append 去重，
            标量字段（current_goal / next_action）直接覆盖，
            preferences 嵌套 merge。中文偏好值会自动归一化
            （如 "实习"→INTERN、"北京市"→"北京"）。

            Args:
                updates: 要更新的字段和值，例如：
                    {"current_goal": "字节深圳产品岗",
                     "open_questions": ["用户是否接受实习转正？"],
                     "next_action": "搜索匹配岗位",
                     "preferences": {"target_roles": ["产品经理"], "locations": ["深圳"]}}
                mode: "merge"（默认，append 去重）或 "replace"（覆盖指定偏好字段）。
                    用户修正之前的偏好时用 replace，例如：
                    update_session_memory(
                        {"preferences": {"locations": ["上海"]}}, mode="replace")
                    会把 locations 从 ["北京"] 变成 ["上海"]

                preferences.recruitment_types 合法枚举（中文会自动映射）：
                    - INTERN（实习/实习生）
                    - GRADUATE（校招/应届）
                    - EXPERIENCED（社招）

            Returns:
                更新结果 JSON
            """
            try:
                # 校验 mode 参数
                if mode not in ("merge", "replace"):
                    return json.dumps({"status": "error", "error": f"Invalid mode: {mode}. Use 'merge' or 'replace'."}, ensure_ascii=False)

                # ✅ 偏好归一化：中文枚举/城市名 → schema 合法值，避免 pydantic 拒绝
                updates, dropped_fields = _normalize_preference_updates(updates)

                async with AsyncSessionLocal() as db_session:
                    memory_service = MemoryService(
                        db=db_session,
                        base_dir=self.intent_file_service.base_dir,
                    )
                    current = await memory_service.get_or_init_session_memory(
                        uuid.UUID(user_id), session_id
                    )
                    merged = await memory_service.merge_session_updates(current, updates, mode=mode)
                    await memory_service.write_session_memory(
                        uuid.UUID(user_id), session_id, merged
                    )
                    return json.dumps({
                        "status": "updated",
                        "mode": mode,
                        "current_goal": merged.current_goal,
                        "next_action": merged.next_action,
                        "open_questions_count": len(merged.open_questions),
                        **({"dropped_fields": dropped_fields} if dropped_fields else {}),
                    }, ensure_ascii=False)
            except Exception as e:
                logger.error("update_session_memory_failed", error=str(e))
                return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)

        # ═══════════════════════════════════════════════════════
        # ✅ 新增工具：update_user_memory（闭包风格）
        # ═══════════════════════════════════════════════════════
        @tool
        async def update_user_memory(updates: dict) -> str:
            """更新用户长期记忆（L2）。

            适用于跨会话仍成立的稳定事实，如长期意向城市、目标岗位、求职方向。
            本次会话内的临时偏好请用 `update_session_memory`。

            写入按来源仲裁：你（agent）的写入不会覆盖用户在设置页显式确认的偏好；
            返回的 written_fields 只包含本次真正生效的字段，未在其中即被跳过。

            Args:
                updates: 要更新的字段和值，例如
                    {"long_term_preferences": {"locations": ["上海"], "target_roles": ["算法工程师"]}}
                    {"career_direction": "往推荐算法方向发展"}

            Returns:
                更新结果 JSON
            """
            try:
                async with AsyncSessionLocal() as db_session:
                    memory_service = MemoryService(
                        db=db_session,
                        base_dir=self.intent_file_service.base_dir,
                    )
                    current = await memory_service.get_user_memory(uuid.UUID(user_id))
                    if not current:
                        current = UserMemory()
                    # 带来源仲裁：L2 现在有多个写入方（业务代码 + agent + 简历抽取），
                    # 不仲裁则简历重解析会整体抹掉对话里积累的偏好
                    merged = await memory_service.merge_with_source(
                        current, updates, source="agent"
                    )
                    await memory_service.write_user_memory(uuid.UUID(user_id), merged)
                    written_sources = merged.preference_sources
                    return json.dumps({
                        "status": "updated",
                        "career_direction": merged.career_direction,
                        "written_fields": [
                            k for k, v in written_sources.items() if v == "agent"
                        ],
                    }, ensure_ascii=False)
            except Exception as e:
                logger.error("update_user_memory_failed", error=str(e))
                return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)

        tools = [search_jobs, get_user_profile, analyze_job_match, update_session_memory, update_user_memory]

        # 路径口径统一（D14）：prompt 里一律用**虚拟绝对路径**，不带 `user-{id}/` 前缀。
        # FilesystemBackend 的 root_dir 已经是 user-{id}，virtual_mode=True 下再拼一层
        # 前缀会被解成 user-{id}/user-{id}/… 而静默 not found（旧版靠 agent `ls` 自愈才没出事）
        profile_path = "/memory/profile.md"
        resume_path = "/resume/active.md"
        session_path = f"/session-{session_id}.md"

        # System prompt for the agent
        # 职责边界（用途治理，api-abuse-protection design.md 7.2）：
        # 软约束，引导无意识偏题用户，不做对抗性防御（由每日配额兜底）。
        # 本段全为**稳定内容**（Phase 4.1）：原先每轮拼的动态 system message（长期偏好
        # + 路径说明）已删除，否则 checkpointer 下 add_messages 会按 id 滚雪球重复追加
        system_prompt = (
            "你是一个专业的求职助手，通过多轮对话帮助用户找到契合的岗位。\n\n"
            "【职责边界】你专注于求职领域的智能帮助：职业规划、岗位分析、简历优化、面试准备等。"
            "对于与求职明显无关的请求（如代写作业、通用写作、代码代做、闲聊灌水），"
            "请礼貌说明你只提供求职帮助，并把话题引导回求职场景。"
            "注意：与求职沾边的边缘请求（如润色实习报告）应当协助。\n\n"

            "【核心工作流程】\n"
            "1. **理解意图**：分析用户消息，提取求职意向（城市/岗位/薪资等）\n"
            "2. **判断是否搜索**：\n"
            "   - 如果信息足够（至少有岗位关键词），立即搜索\n"
            "   - 如果信息不足，最多问1-2个澄清问题\n"
            "   - 如果用户不耐烦，基于已有信息搜索\n"
            f"3. **搜索前先读长期画像**：调用 search_jobs 前先 `read_file` `{profile_path}`，"
            "把里面的长期偏好带入搜索\n"
            "4. **执行搜索**：调用 search_jobs，默认纳入用户简历信息\n"
            "5. **解读结果**：分析匹配度，指出优势和差距\n\n"

            "【记忆与文件视图】（最高优先级规则）\n"
            "你看到的内容分三层，**读写方式完全不同**：\n\n"
            f"1. `{session_path}`（L1 对话状态，可读写）:\n"
            "   - 职责: 记录当前目标、确认偏好、待办问题\n"
            "   - 章节: 目标(current_goal) / 偏好(preferences) / 偏好来源 / 待回答问题(open_questions) / 近期决策 / next_action\n"
            "   - 更新方式: 用 `update_session_memory` 工具（自动同步 markdown 与数据库），"
            "写 markdown 文件只作为兜底\n\n"
            f"2. `{profile_path}`（L2 长期画像，**只读**）:\n"
            "   - 职责: 跨会话仍成立的长期偏好与求职方向\n"
            "   - 章节: 长期偏好(long_term_preferences) / 偏好来源(preference_sources) / 负面信号 / 求职方向\n"
            "   - 由系统从数据库实时渲染，`write_file` / `edit_file` 改不了它\n"
            "   - 需要更新时用 `update_user_memory` 工具（写入按来源仲裁："
            "用户显式确认的偏好不会被你覆盖，返回的 written_fields 才是真正生效的字段）\n\n"
            f"3. `{resume_path}`（当前启用的简历，**只读**）:\n"
            "   - 职责: 用户背景与能力画像，回答时可直接引用\n"
            "   - 同样是实时渲染；未上传简历时返回占位文本，此时应鼓励用户上传\n\n"
            "**冷启动兜底**（重要）: 若本轮看不到本会话的历史消息（如会话被重新打开），"
            f"先 `read_file` `{session_path}` 恢复上下文再行动，绝不凭空假设用户说过什么\n\n"

            "【偏好捕捉规则】\n"
            "当用户在对话中透露求职偏好信息时，立即调用 update_session_memory 记录，\n"
            "不要等到搜索时才更新。包括：\n"
            "- 目标岗位 → preferences.target_roles\n"
            "- 城市 → preferences.locations\n"
            "- 薪资期望 → preferences.salary\n"
            "- 招聘类型（校招/实习/社招）→ preferences.recruitment_types\n"
            "- 行业偏好 → preferences.industries\n"
            "- 技能关键词 → preferences.skills\n\n"
            "【面向用户的表达规范】（重要）\n"
            "- 绝不向用户输出内部术语：枚举值（如 INTERN/GRADUATE/EXPERIENCED）、工具名、\n"
            "  字段名、JSON 等。用户语言中应该说“实习”“校招”“社招”\n"
            "- 时态要准确：进行中的动作说“正在XXX...”，已完成的动作说“已为你XXX”，\n"
            "  绝不混用（如“已为你正在读取”是病句）\n"
            "- 工具调用结果只用于你决策，不要原样复述给用户\n\n"
            "【会话上下文规则】\n"
            "- 恢复旧会话后发现用户新消息与历史话题明显不同（如从产品经理切到算法），\n"
            "  先用一句话确认（“刚才我们在聊X，现在想切到Y对吗？”），得到确认后再按新话题行动\n"
            "- 用户直接给出上一轮追问的答案时，先消化答案并继续任务，绝不原样重复上一轮的追问\n\n"
            "用户修正之前的偏好时（如“算了，上海吧”），用 replace 模式：\n"
            'update_session_memory({"preferences": {"locations": ["上海"]}}, mode="replace")\n\n'

            "【搜索时的信息分流】\n"
            "调用 search_jobs 时，信息按以下通道分流：\n\n"
            "1. query 参数：只填目标岗位名称（1-3个词）\n"
            '   ✅ "产品经理"、"Java后端"、"数据分析"\n'
            '   ❌ "北京产品经理 5年经验"（城市/经验走 preferences）\n\n'
            "2. 结构化偏好：通过 update_session_memory 维护，search_jobs 会自动读取\n\n"
            "3. 简历与长期偏好：无需在 query 里重复，后端会自动结合\n\n"
            "search_jobs 工具会自动读取你维护的 SessionMemory.preferences，\n"
            "与 query 一起融合成 JD 视角的检索 query。你不需要在 query 里重复 preferences 的信息。\n\n"

            "【会话隔离】\n"
            f"- 你的文件根目录就是当前用户目录，`ls` 可直接看到 `{session_path}` 与该用户的其他会话文件\n"
            "- 其他 `session-*.md` 属于该用户的其他会话（可能涉及隐私），请只关注当前会话文件\n\n"

            "【重要规则】\n"
            "- 不要每轮都问问题！如果用户说了岗位关键词，直接搜索\n"
            "- **简历信息的使用方式**（重要）：\n"
            "   - ✅ 作为对话上下文：理解用户能力，在回复中提及（如'根据您的Python经验...'）\n"
            "   - ❌ 不作为搜索条件：除非用户明确要求'只找XX技能的岗位'，否则不添加到 filters\n"
            "   -  后端自动处理：search_jobs 工具会在后端层面结合简历信息进行匹配度计算\n"
            "- 如果用户还没上传简历，主动鼓励用户上传\n"
            "- 搜索结果最多展示5个岗位，简洁解读\n"
            "- 如果用户切换求职方向（如从'算法'转到'产品'），重新搜索\n\n"

            "【处理 search_jobs 返回结果】\n"
            "工具返回的岗位数据会由后端独立推送给前端，你无需在回复中输出 JSON。\n"
            "你的任务：用 1-2 句自然语言向用户解读（例如「找到 5 个岗位，匹配度 70-90%，最匹配的是 XX 公司的 XX 岗位」）。\n"
            "不要在回复中输出 JSON 代码块或岗位列表文本。\n\n"

            "【输出格式规则】（严格遵守）\n"
            "- ✅ 只输出面向用户的最终回复，简洁专业\n"
            "- ❌ 绝不输出内部推理过程（如'让我检查一下文件'、'让我读取画像'等）\n"
            "- ❌ 绝不提及文件操作（读取、写入、更新记忆文件）\n"
            "- ✅ 始终使用中文进行思考和回复\n"
            "- ❌ 绝不输出英文文本\n"
            "- ✅ 搜索结果用 1-2 句话自然解读，不重复 JSON 数据\n\n"

            "【对话风格】\n"
            "- 简洁、专业、有同理心\n"
            "- 避免机械式提问，像真人顾问一样自然交流\n"
            "- 主动告知用户：'我已将你的简历纳入搜索条件'\n\n"

            "【记忆工具使用指南】\n"
            "- 更新对话状态（首选）：`update_session_memory(updates: dict)`，无需手动 write_file\n"
            f"- 更新长期偏好：`update_user_memory(updates: dict)`（直接写 `{profile_path}` 会被拒）\n"
            "- 跨会话仍成立的事实才写长期偏好（“我以后都只想…”）；"
            "本次会话的临时探索留在 session memory，别误写长期记忆\n"
            "- 字段名用 Pydantic schema 命名：target_roles / locations / salary.min / career_direction"
        )

        # FilesystemBackend root_dir 设为 user 目录，agent 直接访问 session 文件与 offload 文件
        # （profile.md / active.md 不在磁盘上，由下面的 DbBackend 路由提供）
        if user_id:
            current_user_dir = self.intent_file_service.base_dir / f"user-{user_id}"
            # 必须先 mkdir：DeepAgents FilesystemBackend 在 virtual_mode=True 下
            # 对不存在的 root_dir 行为未定义，提前建好避免初始化失败
            current_user_dir.mkdir(parents=True, exist_ok=True)

            filesystem_backend = FilesystemBackend(
                root_dir=str(current_user_dir),
                max_file_size_mb=10,
                virtual_mode=True
            )
            logger.info("filesystem_backend_created", user_id=user_id, root_dir=str(current_user_dir))
        else:
            filesystem_backend = FilesystemBackend(
                root_dir=self.intent_file_service.base_dir,
                max_file_size_mb=10,
                virtual_mode=True
            )

        # ✅ Phase 2.3：简历与长期记忆走 DbBackend（按需渲染、不落盘），
        # 其余路径（session-*.md / offload 文件）仍走 FilesystemBackend。
        # 无 user_id 时无法限定查询范围，不挂路由。
        if user_id:
            db_backend = DbBackend(
                user_id=user_id,
                session_factory=AsyncSessionLocal,
                base_dir=self.intent_file_service.base_dir,
            )
            filesystem_backend = CompositeBackend(
                default=filesystem_backend,
                routes={"/resume/": db_backend, "/memory/": db_backend},
                # summarization offload 单独归到 /artifacts/ 下，
                # 避免与 session-*.md 同层混在一起
                artifacts_root="/artifacts/",
            )

        agent = create_deep_agent(
            model=self.llm_service.chat_model,
            tools=tools,
            system_prompt=system_prompt,
            backend=filesystem_backend,  # Pass backend directly, not as middleware
            checkpointer=checkpointer,  # Enable persistence if checkpointer provided
        )

        return agent


    async def _prepare_messages(self, message: str, session_id: str, user_id: str | None = None):
        """Shared preparation logic for chat() and chat_stream().

        开关开启（有 checkpointer）：跨轮上下文由框架从 checkpoint 恢复，
        只传本轮用户消息，**不再拼动态 system message、不再重建历史**（D3/D4）。
        开关关闭：回滚路径，仍从 chat_messages 全量重建历史（不含旧的
        【用户长期偏好】/【当前用户文件路径】注入，那两部分已迁入 system_prompt）。

        Returns:
            tuple: (agent, config, messages)
        """
        # ✅ 动态创建 Agent，传入 session_id 和 user_id
        # checkpointer 来自进程级 factory（Phase 1.2）；开关关闭或未初始化时
        # 为 None，下面的全量重建分支作为回滚路径保留（design.md「迁移与回滚」）
        settings = get_settings()
        checkpointer = get_checkpointer() if settings.ENABLE_AGENT_CHECKPOINTER else None
        agent = self._create_agent(
            session_id=session_id,
            user_id=user_id,
            checkpointer=checkpointer,
        )

        # recursion_limit（Phase 4.1）：原来依赖 langgraph 默认 25，多工具链路
        # （读画像 → 搜索 → 解读 → 再搜索）容易碰顶后以 GraphRecursionError 收场
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": settings.AGENT_RECURSION_LIMIT,
        }

        # ════════════════════════════════════════════════════
        # ✅ 有 checkpointer：跨轮状态由框架恢复，只传本轮消息（D3/D4）
        # 此处**不能**再注入动态 system message，也不能重建历史：
        # add_messages 按 id 合并，每轮新生成的 system message / 历史消息 id 不同
        # → 会滚雪球式重复追加进 checkpoint
        # ════════════════════════════════════════════════════
        if checkpointer is not None:
            return agent, config, [{"role": "user", "content": message}]

        # ════════════════════════════════════════════════════
        # 回滚分支：开关关闭时从 chat_messages 全量重建历史
        # （原动态 system message 已删除：长期偏好改读 /memory/profile.md，
        #   路径说明已进 system_prompt；两份真理源不会再出现不同步）
        # ════════════════════════════════════════════════════
        history_messages = []
        try:
            async with AsyncSessionLocal() as db_session:
                from app.models import ChatMessage as ChatMessageModel
                result = await db_session.execute(
                    select(ChatMessageModel)
                    .where(ChatMessageModel.session_id == uuid.UUID(session_id))
                    .order_by(ChatMessageModel.created_at.asc())
                )
                db_messages = result.scalars().all()

                for msg in db_messages:
                    if msg.role not in ("user", "assistant"):
                        continue
                    content = msg.content or ""
                    if not content.strip():
                        continue

                    # 不再拼接 _build_tool_context 摘要：那是无 checkpointer 时
                    # 让 agent 能看到“上轮搜了哪些岗位”的补偿手段，
                    # 上 checkpoint 后 ToolMessage 本体已完整保留
                    history_messages.append({"role": msg.role, "content": content})
        except Exception as e:
            logger.warning("failed_to_load_conversation_history", error=str(e))

        messages = history_messages

        # 兜底：历史加载失败时，至少要有当前消息
        if not any(m["role"] == "user" for m in messages):
            messages.append({"role": "user", "content": message})

        return agent, config, messages

    # 注：原 `_build_tool_context`（从 message_metadata 拼工具调用摘要进历史）已随
    # agent-context-overhaul Phase 4.1 删除：上 checkpointer 后 ToolMessage 本体
    # 完整保留在 checkpoint 里，不再需要这种有损补偿

    async def chat_stream(
        self,
        message: str,
        session_id: str,
        user_id: str | None = None
    ):
        """True streaming via astream_events (SSE protocol).

        Yields events: token, job_results, tool_calls, tool_results, final_response, error
        """
        try:
            logger.info(
                "chat_stream_request_received",
                session_id=session_id,
                user_id=user_id,
                message_length=len(message),
                message_preview=message[:100]
            )

            agent, config, messages = await self._prepare_messages(message, session_id, user_id)
            full_response = ""

            # ✅ 收集工具调用和结果，用于持久化到 message_metadata
            tool_calls_log = []   # [{"name": "search_jobs", "args": {...}}]
            tool_results_log = [] # [{"name": "search_jobs", "result": "..."}]
            # ✅ Phase 5.1：本轮各次模型调用的 cache 命中情况
            cache_usages: list[dict] = []

            # ✅ 工具中文描述映射（用于前端卡片显示）
            TOOL_DISPLAY_NAMES = {
                "search_jobs": "正在搜索匹配岗位",
                "read_file": "正在读取记忆文件",
                "write_file": "正在更新记忆文件",
                "edit_file": "正在更新记忆文件",
                "get_user_profile": "正在查阅用户偏好",
                "ls": "正在浏览文件目录",
                "update_session_memory": "正在更新偏好档案",
                "update_user_memory": "正在更新长期偏好",
                "analyze_job_match": "正在分析岗位匹配",
            }

            logger.info("starting_chat_stream")

            # Use astream_events for fine-grained true streaming
            async for event in agent.astream_events(
                {"messages": messages},
                config=config,
                version="v2"
            ):
                event_type = event.get("event")

                if event_type == "on_chat_model_stream":
                    # ✅ 过滤双发/内部流：deepagents 链路下内层模型与内部
                    # LLM 调用（如 QueryFormulator）的 token 事件一并丢弃，
                    # 只保留外层主模型的事件（详见 __init__ 注释）
                    if event.get("name") != self._stream_source_name:
                        continue
                    chunk = event.get("data", {}).get("chunk")
                    # ✅ 过滤空 token：LLM 生成 tool_calls 时 chunk.content 为空字符串
                    if chunk and chunk.content:
                        full_response += chunk.content
                        yield {"type": "token", "data": chunk.content}

                elif event_type == "on_chat_model_end":
                    # 只统计外层主模型的调用（过滤理由同 on_chat_model_stream）：
                    # 内部 QueryFormulator 与摘要调用均显式传 callbacks=[]，
                    # 不经过这里；但万一供应商名变化，过滤能避免统计被污染
                    if event.get("name") != self._stream_source_name:
                        continue
                    usage = extract_prompt_cache_usage(
                        event.get("data", {}).get("output")
                    )
                    if usage is not None:
                        cache_usages.append(usage)

                elif event_type == "on_tool_start":
                    # ✅ 收集工具调用参数 + 推送 tool_start 事件
                    tool_name = event.get("name", "")
                    tool_input = event.get("data", {}).get("input", {})
                    tool_calls_log.append({"name": tool_name, "args": tool_input})
                    display = TOOL_DISPLAY_NAMES.get(tool_name, "正在处理你的请求")
                    yield {"type": "tool_start", "data": {"name": tool_name, "display": display}}

                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "")
                    output = event.get("data", {}).get("output")
                    # ✅ 处理 ToolMessage 对象：@tool 返回字符串时 LangChain 自动包装为 ToolMessage
                    output_str = output.content if hasattr(output, 'content') else str(output) if output else ""

                    # 收集所有工具结果
                    tool_results_log.append({"name": tool_name, "result": output_str})

                    # 推送 tool_end 事件
                    yield {"type": "tool_end", "data": {"name": tool_name}}

                    # 特殊处理 search_jobs → 推送结构化数据到前端
                    if tool_name == "search_jobs":
                        try:
                            parsed = json.loads(output_str)
                            if parsed.get("type") == "job_search_results":
                                yield {"type": "job_results", "data": parsed}
                        except (json.JSONDecodeError, AttributeError, TypeError):
                            pass

            logger.info(
                "chat_stream_completed",
                session_id=session_id,
                response_length=len(full_response)
            )
            _log_prompt_cache_usage(session_id, cache_usages)

            # ✅ yield 工具调用数据供 API 层持久化
            if tool_calls_log:
                yield {"type": "tool_calls", "data": tool_calls_log}
            if tool_results_log:
                yield {"type": "tool_results", "data": tool_results_log}

            yield {"type": "final_response", "data": full_response}

        except Exception as e:
            logger.error(
                "chat_stream_failed",
                session_id=session_id,
                error=str(e)
            )
            yield {"type": "error", "data": str(e)}

    async def chat(
        self,
        message: str,
        session_id: str,
        user_id: str | None = None
    ) -> str:
        """
        Process a chat message and return response (non-streaming, for deprecated endpoint)

        Args:
            message: User's message
            session_id: Unique session ID for conversation history
            user_id: Optional user ID for personalization

        Returns:
            Agent's response
        """
        logger.info(
            "chat_request_received",
            session_id=session_id,
            user_id=user_id,
            message_length=len(message),
            message_preview=message[:100]
        )

        agent, config, messages = await self._prepare_messages(message, session_id, user_id)

        # Run the agent
        logger.info("starting_chat_invoke")

        try:
            response = await agent.ainvoke(
                {"messages": messages},
                config=config
            )

            # Extract the last AI message
            ai_message = response["messages"][-1]
            response_content = ai_message.content if hasattr(ai_message, 'content') else str(ai_message)

            # ✅ Phase 5.1：非流式入口同样要能看 cache 命中（一次拉全部消息）
            cache_usages = [
                u
                for u in (
                    extract_prompt_cache_usage(m)
                    for m in response["messages"]
                    if isinstance(m, AIMessage)
                )
                if u is not None
            ]

            logger.info(
                "chat_stream_completed",
                session_id=session_id,
                response_length=len(response_content)
            )
            _log_prompt_cache_usage(session_id, cache_usages)

            return response_content
        except Exception as e:
            logger.error(
                "chat_stream_failed",
                session_id=session_id,
                error=str(e)
            )
            raise
