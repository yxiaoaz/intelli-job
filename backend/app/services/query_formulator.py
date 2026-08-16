"""QueryFormulator — LLM 融合的 JD 视角 query 生成模块。

合并并替代 QueryEnhancer 的职责：
- 生成 JD 视角的 expanded_query（embedding 友好）
- 生成 synonyms（前端展示用）
- 简历能力激活（只纳入与求职意图相关的技能）
- 缓存 + 降级兜底
"""
import json
import re
from typing import Any

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.memory.schemas import JobPreference, UserMemory
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger()


class QueryFormulator:
    """LLM query 融合服务 — 生成 JD 视角的检索 query。"""

    # 类变量：所有实例共享同一份缓存
    _shared_cache: dict[str, dict] = {}

    def __init__(self):
        self._model = ChatOpenAI(
            model=settings.LLM_COMPLETION_API_MODEL_NAME,
            temperature=0,
            api_key=settings.LLM_COMPLETION_API_KEY,
            base_url=settings.LLM_COMPLETION_API_URL,
        )

    # ── 主入口 ──────────────────────────────────────────────────────────

    async def formulate(
        self,
        natural_query: str,
        session_preferences: JobPreference | None = None,
        preference_sources: dict[str, str] | None = None,
        user_memory: UserMemory | None = None,
        resume_profile: dict[str, Any] | None = None,
        resume_id: str | None = None,
        hard_filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """生成 JD 视角的检索 query。

        Returns:
            {
                "expanded_query": "负责 B 端产品规划与设计...",
                "synonyms": ["B端产品经理", "PM", "产品策划"],
                "original_keywords": "<natural_query>"
            }
        """
        if session_preferences is None:
            session_preferences = JobPreference()
        if preference_sources is None:
            preference_sources = {}
        if resume_profile is None:
            resume_profile = {}
        if hard_filters is None:
            hard_filters = {}

        # 1. 输入校验：三路目标岗位信号
        target_role = self._resolve_target_role(
            natural_query, session_preferences, user_memory
        )
        if not target_role:
            # 三路都空 → 退化为原始 query
            return {
                "expanded_query": natural_query,
                "synonyms": [],
                "original_keywords": natural_query,
            }

        # 2. 缓存检查
        cache_key = self._build_cache_key(
            natural_query, session_preferences, resume_profile, resume_id
        )
        if cache_key in self._shared_cache:
            logger.info("query_formulator_cache_hit", query=natural_query)
            return self._shared_cache[cache_key]

        # 3. LLM 调用
        try:
            result = await self._call_llm(
                natural_query=natural_query,
                session_preferences=session_preferences,
                preference_sources=preference_sources,
                user_memory=user_memory,
                resume_profile=resume_profile,
            )
            result["original_keywords"] = natural_query
            self._shared_cache[cache_key] = result
            logger.info(
                "query_formulator_success",
                query=natural_query,
                expanded=result["expanded_query"][:100],
            )
            return result
        except Exception as e:
            logger.warning("query_formulator_failed", error=str(e))
            # 降级为 S1 机械拼接
            degraded = self._degrade_to_s1(
                natural_query, session_preferences, resume_profile
            )
            degraded["original_keywords"] = natural_query
            return degraded

    # ── 三路目标岗位信号解析 ────────────────────────────────────────────

    def _resolve_target_role(
        self,
        natural_query: str,
        session_preferences: JobPreference,
        user_memory: UserMemory | None,
    ) -> str | None:
        """按优先级解析目标岗位信号：preferences → query 规则抽取 → career_direction"""
        if session_preferences.target_roles:
            return ", ".join(session_preferences.target_roles)

        extracted = self._extract_role_from_query(natural_query)
        if extracted:
            return extracted

        if user_memory and user_memory.career_direction:
            return user_memory.career_direction

        return None

    @staticmethod
    def _extract_role_from_query(query: str) -> str | None:
        """从自然语言 query 中规则抽取岗位名称。

        匹配常见岗位名模式，返回第一个匹配或 None。
        """
        if not query or not query.strip():
            return None

        # 常见岗位关键词（按长度降序，优先匹配更长的）
        role_patterns = [
            r"(?:资深|高级|初级|中级)?\s*(?:AI|后端|前端|全栈|数据|算法|测试|运维)?\s*"
            r"(?:产品经理|产品总监|产品专员|产品策划|产品经理助理)",
            r"(?:资深|高级|初级|中级)?\s*(?:Java|Python|Go|Golang|Rust|C\+\+|前端|后端|全栈|移动)?\s*"
            r"(?:工程师|开发|架构师|技术专家)",
            r"(?:资深|高级|初级)?\s*(?:数据分析师|数据工程师|数据科学家|BI分析师|算法工程师)",
            r"(?:资深|高级)?\s*(?:UI设计师|UX设计师|交互设计师|视觉设计师|平面设计师)",
            r"(?:资深|高级)?\s*(?:运营经理|运营专员|用户运营|内容运营|社区运营|市场经理)",
            r"(?:HR|HRBP|人力资源|招聘专员|薪酬专员|培训专员)",
            r"(?:项目经理|PMO|Scrum\s*Master|敏捷教练)",
            r"(?:财务|会计|审计|税务|出纳)",
            r"(?:销售|商务|BD|客户经理|大客户经理)",
        ]

        for pattern in role_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(0).strip()

        # 兜底：如果 query 很短（<=10 字），直接作为岗位名
        stripped = query.strip()
        if len(stripped) <= 10:
            return stripped

        return None

    # ── 缓存 key ────────────────────────────────────────────────────────

    @staticmethod
    def _build_cache_key(
        natural_query: str,
        session_preferences: JobPreference,
        resume_profile: dict,
        resume_id: str | None = None,
    ) -> str:
        base = natural_query.strip().lower()
        pref_keys = []
        if session_preferences.target_roles:
            pref_keys.append("roles:" + ",".join(session_preferences.target_roles))
        if session_preferences.locations:
            pref_keys.append("locs:" + ",".join(session_preferences.locations))
        if session_preferences.salary:
            pref_keys.append(f"sal:{session_preferences.salary.min}")
        resume_key = resume_id or ""
        return f"{base}|{'|'.join(pref_keys)}|{resume_key}"

    # ── LLM 调用 ────────────────────────────────────────────────────────

    async def _call_llm(
        self,
        natural_query: str,
        session_preferences: JobPreference,
        preference_sources: dict[str, str],
        user_memory: UserMemory | None,
        resume_profile: dict,
    ) -> dict[str, Any]:
        messages = self._build_messages(
            natural_query, session_preferences, preference_sources,
            user_memory, resume_profile,
        )
        response = await self._model.ainvoke(messages)
        raw = response.content.strip()

        # 解析 JSON（兼容 markdown code block）
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        parsed = json.loads(raw)
        return {
            "expanded_query": parsed.get("expanded_query", natural_query),
            "synonyms": parsed.get("synonyms", []),
        }

    def _build_messages(
        self,
        natural_query: str,
        session_preferences: JobPreference,
        preference_sources: dict[str, str],
        user_memory: UserMemory | None,
        resume_profile: dict,
    ) -> list[dict]:
        # 简历摘要
        resume_parts = []
        if resume_profile.get("skills"):
            skills = resume_profile["skills"]
            resume_parts.append(f"技能: {', '.join(skills[:10]) if isinstance(skills, list) else skills}")
        if resume_profile.get("latest_title") or resume_profile.get("latest_company"):
            title = resume_profile.get("latest_title", "")
            company = resume_profile.get("latest_company", "")
            resume_parts.append(f"最近职位: {title} @ {company}")
        if resume_profile.get("degree"):
            resume_parts.append(f"学历: {resume_profile['degree']}")
        if resume_profile.get("school"):
            resume_parts.append(f"学校: {resume_profile['school']}")
        resume_text = "\n".join(resume_parts) if resume_parts else "（无简历信息）"

        # 结构化偏好
        pref_parts = []
        if session_preferences.target_roles:
            pref_parts.append(f"目标岗位: {', '.join(session_preferences.target_roles)}")
        if session_preferences.locations:
            pref_parts.append(f"期望城市: {', '.join(session_preferences.locations)}")
        if session_preferences.recruitment_types:
            pref_parts.append(f"招聘类型: {', '.join(session_preferences.recruitment_types)}")
        if session_preferences.industries:
            pref_parts.append(f"行业偏好: {', '.join(session_preferences.industries)}")
        if session_preferences.skills:
            pref_parts.append(f"技能偏好: {', '.join(session_preferences.skills)}")
        if session_preferences.salary:
            pref_parts.append(f"薪资期望: {session_preferences.salary.min}+ {session_preferences.salary.currency}")
        pref_text = "\n".join(pref_parts) if pref_parts else "（未设定）"

        # 偏好来源
        sources_text = ", ".join(f"{k}={v}" for k, v in preference_sources.items()) if preference_sources else "（无）"

        # 用户长期记忆
        memory_parts = []
        if user_memory:
            if user_memory.stable_facts:
                facts = user_memory.stable_facts
                if facts.get("current_title"):
                    memory_parts.append(f"当前职位: {facts['current_title']}")
                if facts.get("education_level"):
                    memory_parts.append(f"学历: {facts['education_level']}")
            if user_memory.career_direction:
                memory_parts.append(f"求职方向: {user_memory.career_direction}")
            if user_memory.long_term_preferences:
                ltp = user_memory.long_term_preferences
                if ltp.target_roles:
                    memory_parts.append(f"长期目标岗位: {', '.join(ltp.target_roles)}")
                if ltp.locations:
                    memory_parts.append(f"长期期望城市: {', '.join(ltp.locations)}")
        memory_text = "\n".join(memory_parts) if memory_parts else "（无长期记忆）"

        system_prompt = (
            "你正在为一位求职者构造用于岗位检索的 query 文本。\n\n"
            f"【用户简历摘要】\n{resume_text}\n\n"
            f"【用户本轮求职意图】\n"
            f"目标岗位: {natural_query}\n"
            f"结构化偏好: {pref_text}\n"
            f"偏好来源: {sources_text}\n\n"
            f"【用户长期记忆】\n{memory_text}\n\n"
            "【岗位库的 JD 风格示例】\n"
            '- "负责 XX 产品的规划与设计，需具备用户调研、数据分析能力，3年以上 B 端产品经验"\n'
            '- "参与 XX 系统后端开发，精通 Python/Go，熟悉分布式架构与微服务"\n'
            '- "负责 XX 业务的数据分析与建模，熟练 SQL/Python，有 BI 看板搭建经验"\n\n'
            "【你的任务】\n"
            "写一段 80-150 字的 query 文本，使其 embedding 能与该用户理想岗位的 JD 高度相似。\n\n"
            "【写作规则】\n"
            '1. 以"岗位 JD 视角"写作，不要以"求职者自我介绍"视角：\n'
            '   ❌ "我精通 Python，想做后端开发"\n'
            '   ✅ "负责后端系统设计与开发，精通 Python/Go，熟悉分布式架构与微服务"\n\n'
            "2. 只纳入与求职意图相关的简历能力，无关能力一律舍弃：\n"
            '   - 用户搜"产品经理"时，简历里的 Python 经验通常不相关（除非是技术产品经理）\n'
            '   - 用户搜"后端开发"时，简历里的 Figma 经验不相关\n\n'
            "3. 如果用户简历与意图错位明显（转岗）：\n"
            "   - 意图优先，简历能力作为可迁移能力的修饰\n"
            '   - 例："具备工程思维与技术背景，希望转向产品规划与设计"\n\n'
            "4. 如果用户是应届生（简历无正式工作经验）：\n"
            "   - 突出学历、专业、实习、课程项目\n"
            '   - 弱化"X 年经验"表述\n\n'
            "5. 不要罗列技能清单，要让技能融入职责描述\n\n"
            '6. 城市作为软信号：如果结构化偏好中有期望城市，在 query 文本末尾附上「工作地点：XX」。\n\n'
            "【偏好来源置信度】\n"
            "- user_confirmed / user_stated → 高置信度，必进 query\n"
            "- agent_inferred → 中置信度，进 query 但可被简历信号修正\n"
            "- system_default → 低置信度，仅兜底\n\n"
            "【输出格式】\n"
            "严格以 JSON 返回，不要包含任何其他文字：\n"
            '{"expanded_query": "JD 视角的 query 段落", "synonyms": ["同义词1", "同义词2", "同义词3"]}'
        )

        user_prompt = "请基于以上信息生成 query。"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    # ── 降级路径 ────────────────────────────────────────────────────────

    @staticmethod
    def _degrade_to_s1(
        natural_query: str,
        session_preferences: JobPreference,
        resume_profile: dict,
    ) -> dict[str, Any]:
        """降级为 S1 机械拼接（与 JobMatchingService._format_user_input 对齐）。"""
        parts = [f"求职偏好: keywords: {natural_query}"]

        if session_preferences.target_roles:
            parts.append(f"target_roles: {', '.join(session_preferences.target_roles)}")
        if session_preferences.locations:
            parts.append(f"locations: {', '.join(session_preferences.locations)}")

        if resume_profile.get("skills"):
            skills = resume_profile["skills"]
            skills_str = ", ".join(skills[:8]) if isinstance(skills, list) else str(skills)
            parts.append(f"\n简历信息: skills: {skills_str}")
        if resume_profile.get("latest_title") or resume_profile.get("latest_company"):
            title = resume_profile.get("latest_title", "")
            company = resume_profile.get("latest_company", "")
            parts.append(f"最近职位: {title} @ {company}")
        if resume_profile.get("degree"):
            parts.append(f"学历: {resume_profile['degree']}")

        expanded = " ".join(parts)
        return {
            "expanded_query": expanded,
            "synonyms": [],
        }
