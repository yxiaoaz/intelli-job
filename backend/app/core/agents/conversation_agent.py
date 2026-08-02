from deepagents import create_deep_agent, FilesystemMiddleware
from deepagents.backends import FilesystemBackend
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy import select
from app.services.llm_service import LLMService
from app.services.job_matching_service import JobMatchingService
from app.services.intent_file_service import IntentFileService
from app.repositories.user_repo import UserRepository
from app.repositories.job_repo import BookmarkRepository, JobRepository
from app.repositories.session_intent_repo import SessionIntentRepository
from app.database import AsyncSessionLocal
from app.utils.logger import get_logger
import uuid
import json
import shutil

logger = get_logger()


class ConversationAgent:
    """DeepAgent for conversational job assistance using deepagents framework"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.job_matching_service = JobMatchingService()
        self.intent_file_service = IntentFileService()
        # Agent 将在每次 chat 调用时动态创建，以支持 session 隔离
    
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
            session_id: str = None,
            user_id: str = None
        ) -> str:
            """Search for matching jobs based on query and filters.
            
            Args:
                query: Job search query (e.g., "产品经理 北京")
                filters: Optional filters like recruitment_type
                session_id: Optional session ID to load user intent
                user_id: Optional user ID to load resume profile
            
            Returns:
                Formatted string of job results with match analysis
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
                
                # Create a temporary DB session
                async with AsyncSessionLocal() as db_session:
                    job_repo = JobRepository(db_session)
                    
                    # Note: Intent is now managed by Agent via FilesystemMiddleware
                    # Agent should read intent files and pass relevant info in the query
                    # No need to load intent from database here
                    
                    results = await self.job_matching_service.match_jobs(
                        user_query_preference={"keywords": query},
                        user_resume_profile={},  # TODO: Load resume if needed
                        hard_filters=filters,
                        top_k=10,
                        job_repo=job_repo
                    )
                
                logger.info(
                    "search_jobs_tool_completed",
                    result_count=len(results) if results else 0
                )
                
                if not results:
                    return "没有找到匹配的职位"
                
                # ✅ 返回结构化 JSON 数据（供前端解析）
                jobs_data = []
                for item in results[:5]:  # Top 5 results
                    job = item["job_item"]
                    score = item.get("score", 0)
                    
                    # ✅ 使用完整描述，不截断
                    full_desc = job.description or ""
                    
                    jobs_data.append({
                        "id": str(job.id),
                        "title": job.job_title,
                        "company": job.company_name,
                        "location": job.location,
                        "salary_min": None,  # TODO: 从 salary 字段解析
                        "salary_max": None,
                        "salary_currency": "CNY",
                        "description": full_desc,  # ✅ 完整描述
                        "truncated_description": full_desc[:150] + "..." if len(full_desc) > 150 else full_desc,  # ✅ 截断版用于卡片预览
                        "requirements": [],  # TODO: 从 full_description 提取
                        "url": job.url,
                        "source": job.source.value if hasattr(job.source, 'value') else str(job.source),  # ✅ 修复：使用 source 字段
                        "match_score": round(score * 100, 1),  # 转换为百分比
                        "match_analysis": f"匹配度 {score:.1%}"
                    })
                
                # 返回 JSON 格式的字符串（前端会解析）
                return json.dumps({
                    "type": "job_search_results",
                    "count": len(jobs_data),
                    "jobs": jobs_data
                }, ensure_ascii=False)
            except Exception as e:
                logger.error("search_jobs_tool_failed", error=str(e))
                return f"搜索失败: {str(e)}"
        
        @tool
        async def get_user_profile(user_id: str) -> str:
            """Get user's profile summary including skills and preferences.
            
            Args:
                user_id: User's UUID
            
            Returns:
                Formatted user profile information
            """
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
                Match analysis with recommendations
            """
            try:
                logger.info(
                    "analyze_job_match_tool_called",
                    job_desc_length=len(job_description),
                    skills=user_skills
                )
                
                llm = self.llm_service.chat_model
                prompt = f"""
                分析以下职位描述与用户技能的匹配度：
                
                用户技能: {user_skills}
                
                职位描述:
                {job_description[:1000]}
                
                请提供：
                1. 匹配度评分（0-100）
                2. 主要匹配的技能
                3. 缺失的关键技能
                4. 建议如何提升匹配度
                """
                
                logger.info("calling_llm_for_job_match_analysis")
                response = await llm.ainvoke(prompt)
                
                logger.info(
                    "job_match_analysis_completed",
                    response_length=len(response.content) if hasattr(response, 'content') else 0
                )
                
                return response.content
            except Exception as e:
                logger.error("analyze_job_match_tool_failed", error=str(e))
                return f"分析失败: {str(e)}"
        
        tools = [search_jobs, get_user_profile, analyze_job_match]
        
        # ✅ 构建当前 session 的绝对路径（用于 System Prompt 中的路径说明）
        if user_id and session_id:
            current_session_path = f"user-{user_id}/session-{session_id}"
            profile_path = f"user-{user_id}/profile.md"
        else:
            current_session_path = "user-xxx/session-yyy"
            profile_path = "user-xxx/profile.md"
        
        # System prompt for the agent
        system_prompt = (
            "你是一个专业的求职助手，通过多轮对话帮助用户找到契合的岗位。\n\n"
            
            "【核心工作流程】\n"
            "1. **理解意图**：分析用户消息，提取求职意向（城市/岗位/薪资等）\n"
            "2. **判断是否搜索**：\n"
            "   - 如果信息足够（至少有岗位关键词），立即搜索\n"
            "   - 如果信息不足，最多问1-2个澄清问题\n"
            "   - 如果用户不耐烦，基于已有信息搜索\n"
            "3. **执行搜索**：调用 search_jobs，默认纳入用户简历信息\n"
            "4. **解读结果**：分析匹配度，指出优势和差距\n\n"
            
            "【记忆文件管理架构】（最高优先级规则）\n"
            "你拥有一个文件系统工作台，必须严格遵循以下协议：\n\n"
            
            "1. **session.md (工作记忆)**:\n"
            f"   - 位置: `{current_session_path}/session.md`\n"
            "   - 职责: 记录当前目标、确认偏好、待办问题。\n"
            "   - 格式: Markdown，包含 Current Goal, Confirmed Preferences, Open Questions 等章节。\n\n"
            
            "2. **search_intent.json (搜索契约)**:\n"
            f"   - 位置: `{current_session_path}/search_intent.json`\n"
            "   - 职责: 结构化搜索参数，是 search_jobs 工具的唯一真理来源。\n"
            "   - 格式: JSON，包含 target_roles, locations, salary, experience 等字段。\n\n"
            
            "3. **profile.md (长期画像)**:\n"
            f"   - 位置: `{profile_path}`\n"
            "   - 职责: 存储来自简历的稳定事实和长期确认的偏好。\n"
            "   - **重要**: 这是当前用户的专属档案，请优先读取此文件获取用户背景。\n"
            "   - **注意**: 该文件已同步到当前 session 目录，你可以直接读取 `profile.md`。\n\n"
            
            "4. **events.jsonl (事件流)**:\n"
            f"   - 位置: `{current_session_path}/events.jsonl`\n"
            "   - 职责: Append-only 记录关键交互事件。\n\n"
            
            "【读写协议】\n"
            "- **启动时**: 必须先读取 `session.md` 和 `search_intent.json` 了解上下文。\n"
            "- **读取 Profile 后**: 如果读取了 `profile.md` 并发现用户技能/经验信息，**必须立即更新 `search_intent.json`**，将提取的信息填入对应字段。\n"
            "- **搜索前**: 根据 `search_intent.json` 构造参数，或直接调用工具让后端处理。\n"
            "- **更新时**: 当用户意图改变，同步更新 `session.md` (自然语言) 和 `search_intent.json` (结构化数据)。\n"
            "- **长期偏好更新规则**（重要）：\n"
            "   - ✅ **何时更新 profile.md**：只有当用户明确表达**长期稳定**的偏好时才更新\n"
            "   - ✅ **典型场景**：'我以后都只想...'、'记住我...'、'设为默认...'、'总是...'\n"
            "   - ❌ **不要更新**：临时探索（'我想看看...'）、单次调整（'这次先...'）、假设性问题（'如果...'）\n"
            "   - **如何更新**：调用 `write_file` 方法更新 `profile.md`，只修改用户提到的字段\n"
            "   - **告知用户**：更新后告诉用户'已将XX设为你的长期偏好'\n\n"
            
            "【Session 隔离规则】（重要）\n"
            "- ✅ **只访问当前会话的文件**：你的文件系统根目录已被限制在当前 session 目录下\n"
            "- ✅ **可以访问 profile.md**：用户的长期画像已自动同步到当前 session 目录，你可以直接读取 `profile.md`\n"
            "- ⚠️ **注意**：虽然你可能看到其他文件，但你应该只关注当前 session 相关的文件\n\n"
            
            "【关键操作流程 - 读取简历后必须执行】\n"
            "当你读取了 `profile.md` 并获取用户信息后，**必须立即执行以下步骤**：\n"
            "1. 从 profile.md 中提取以下信息：\n"
            "   - current_title → 放入 search_intent.json 的 filters['current_title']\n"
            "   - skills → 放入 search_intent.json 的 filters['skills']（逗号分隔字符串）\n"
            "   - education_level → 放入 search_intent.json 的 filters['education_level']\n"
            "2. **调用文件系统工具的 write_file 方法**，更新 `search_intent.json`\n"
            "3. 更新后的 JSON 格式示例：\n"
            "```json\n"
            "{\n"
            "  \"target_roles\": [],\n"
            "  \"locations\": [],\n"
            "  \"salary\": null,\n"
            "  \"experience\": null,\n"
            "  \"filters\": {\n"
            "    \"current_title\": \"Python工程师\",\n"
            "    \"skills\": \"Python, SQL, Java, PyTorch, LLM\",\n"
            "    \"education_level\": \"硕士\"\n"
            "  },\n"
            "  \"updated_at\": \"2026-07-12T18:27:00Z\"\n"
            "}\n"
            "```\n"
            "4. **重要**: 这是强制步骤，不更新会导致前端显示'暂无求职意向'！\n\n"
            
            "【长期偏好更新示例】\n"
            "当用户说'我以后都只想找北京的工作'时：\n"
            "1. 识别为长期偏好变更（关键词：'以后都只想'）\n"
            "2. 读取当前 `profile.md`\n"
            "3. 修改 locations 字段为 ['北京']\n"
            "4. 调用 write_file 更新 `profile.md`\n"
            "5. 告知用户：'已将北京设为你的长期意向城市'\n\n"
            "**profile.md 格式示例：**\n"
            "```markdown\n"
            "# User Profile\n\n"
            "## Basic Info\n"
            "- Username: user123\n"
            "- Name: 张三\n\n"
            "## Skills\n"
            "- Python, SQL, Java, PyTorch, LLM\n\n"
            "## Work Experience\n"
            "- 字节跳动 - Python工程师 (2022-2024)\n"
            "- 阿里巴巴 - 算法实习生 (2021-2022)\n\n"
            "## Education\n"
            "- 北京大学 - 计算机科学硕士 (2019-2022)\n\n"
            "## Long-term Preferences\n"
            "- **Locations**: 北京, 上海\n"
            "- **Industries**: 互联网, AI\n"
            "- **Company Types**: 大厂, 外企\n"
            "- **Positions**: 算法工程师, Python工程师\n"
            "- **Salary Min**: 20000\n"
            "- **Remote Preference**: 接受远程\n"
            "```\n\n"
            
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
            "- ❌ 绝不输出内部推理过程（如'让我检查一下文件'、'让我读取profile'等）\n"
            "- ❌ 绝不提及文件操作（读取、写入、更新 session.md/search_intent.json/profile.md）\n"
            "- ✅ 始终使用中文进行思考和回复\n"
            "- ❌ 绝不输出英文文本\n"
            "- ✅ 搜索结果用 1-2 句话自然解读，不重复 JSON 数据\n\n"
            
            "【对话风格】\n"
            "- 简洁、专业、有同理心\n"
            "- 避免机械式提问，像真人顾问一样自然交流\n"
            "- 主动告知用户：'我已将你的简历纳入搜索条件'"
        )
        
        # ✅ Session 隔离：将 FilesystemBackend 的 root_dir 设置为当前 session 目录
        if user_id and session_id:
            # 构建当前 session 的绝对路径
            current_session_dir = self.intent_file_service.base_dir / f"user-{user_id}" / f"session-{session_id}"
            
            # 确保 session 目录存在
            current_session_dir.mkdir(parents=True, exist_ok=True)
            
            filesystem_backend = FilesystemBackend(
                root_dir=str(current_session_dir),  # 限制在当前 session 目录
                max_file_size_mb=10,
                virtual_mode=True  # Enable virtual path semantics for security
            )
            
            logger.info(
                "filesystem_backend_created_with_session_isolation",
                session_id=session_id,
                user_id=user_id,
                root_dir=str(current_session_dir)
            )
        else:
            # Fallback: 如果没有 user_id/session_id，使用 base_dir
            filesystem_backend = FilesystemBackend(
                root_dir=self.intent_file_service.base_dir,
                max_file_size_mb=10,
                virtual_mode=True
            )
        
        agent = create_deep_agent(
            model=self.llm_service.chat_model,
            tools=tools,
            system_prompt=system_prompt,
            backend=filesystem_backend,  # Pass backend directly, not as middleware
            checkpointer=checkpointer,  # Enable persistence if checkpointer provided
        )
        
        return agent
    
    async def _sync_profile_to_session(self, user_id: str, session_id: str) -> None:
        """
        ✅ Session 隔离：将用户的 profile.md 同步到当前 session 目录
        
        这样做的目的：
        1. FilesystemBackend 的 root_dir 可以限制在 session 目录，实现完美隔离
        2. Agent 仍然可以读取 profile.md（从 session 目录下的副本）
        3. 避免 Agent 看到其他 session 的文件
        
        Args:
            user_id: User ID
            session_id: Session ID
        """
        import asyncio
        from pathlib import Path
        
        # 构建路径
        user_dir = self.intent_file_service.base_dir / f"user-{user_id}"
        session_dir = user_dir / f"session-{session_id}"
        source_profile = user_dir / "profile.md"
        target_profile = session_dir / "profile.md"
        
        # 确保 session 目录存在
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查源文件是否存在
        if not source_profile.exists():
            logger.info(
                "profile_not_found",
                session_id=session_id,
                user_id=user_id,
                message="User has no profile.md yet, skipping sync"
            )
            return
        
        # 异步复制文件
        await asyncio.to_thread(
            lambda: shutil.copy2(source_profile, target_profile)
        )
        
        logger.info(
            "profile_synced_to_session",
            session_id=session_id,
            user_id=user_id,
            source=str(source_profile),
            target=str(target_profile)
        )
    
    async def _sync_profile_from_session(self, user_id: str, session_id: str) -> bool:
        """
        ✅ 长期偏好更新：检测 session 目录下的 profile.md 是否有变更，如果有则同步回 user 目录
        
        这样做的目的：
        1. Agent 更新了 session 目录下的 profile.md 副本（表示用户修改了长期偏好）
        2. 需要将变更同步回 user 目录下的真正的 profile.md
        3. 同时更新数据库中的 UserQueryPreference 表
        
        Args:
            user_id: User ID
            session_id: Session ID
            
        Returns:
            bool: 是否发生了同步
        """
        import asyncio
        from pathlib import Path
        
        # 构建路径
        user_dir = self.intent_file_service.base_dir / f"user-{user_id}"
        session_dir = user_dir / f"session-{session_id}"
        source_profile = session_dir / "profile.md"  # session 目录下的副本
        target_profile = user_dir / "profile.md"      # user 目录下的真正文件
        
        # 检查源文件是否存在
        if not source_profile.exists():
            return False
        
        # 如果目标文件不存在，直接复制
        if not target_profile.exists():
            await asyncio.to_thread(lambda: shutil.copy2(source_profile, target_profile))
            logger.info(
                "profile_created_from_session",
                session_id=session_id,
                user_id=user_id,
                source=str(source_profile),
                target=str(target_profile)
            )
            return True
        
        # 比较两个文件的修改时间
        source_mtime = source_profile.stat().st_mtime
        target_mtime = target_profile.stat().st_mtime
        
        # 如果 session 目录下的文件更新，说明 Agent 修改了它
        if source_mtime > target_mtime:
            # 读取两个文件的内容进行比较
            try:
                source_content = await asyncio.to_thread(lambda: source_profile.read_text(encoding='utf-8'))
                target_content = await asyncio.to_thread(lambda: target_profile.read_text(encoding='utf-8'))
                
                # 如果内容不同，说明有变更
                if source_content != target_content:
                    # 同步回 user 目录
                    await asyncio.to_thread(lambda: shutil.copy2(source_profile, target_profile))
                    
                    logger.info(
                        "profile_updated_from_session",
                        session_id=session_id,
                        user_id=user_id,
                        source=str(source_profile),
                        target=str(target_profile),
                        message="Agent updated long-term preferences, synced to user directory"
                    )
                    
                    # TODO: 同时更新数据库中的 UserQueryPreference 表
                    # await self._update_user_preferences_from_profile(user_id, source_content)
                    
                    return True
            except Exception as e:
                logger.error(
                    "profile_sync_error",
                    session_id=session_id,
                    user_id=user_id,
                    error=str(e)
                )
        
        return False

    async def _prepare_messages(self, message: str, session_id: str, user_id: str | None = None):
        """Shared preparation logic for chat() and chat_stream().
        
        Handles: profile sync, agent creation, system message merging,
                 conversation history loading with tool context, KV-cache optimization.
        
        Returns:
            tuple: (agent, config, messages)
        """
        # ✅ Session 隔离：每轮对话前同步 profile.md 到当前 session
        if user_id:
            try:
                await self._sync_profile_to_session(user_id, session_id)
            except Exception as e:
                logger.warning(
                    "profile_sync_failed",
                    session_id=session_id,
                    user_id=user_id,
                    error=str(e)
                )
                # 继续执行，不阻断对话
        
        # ✅ 动态创建 Agent，传入 session_id 和 user_id 以实现 session 隔离
        agent = self._create_agent(session_id=session_id, user_id=user_id)
        
        config = {"configurable": {"thread_id": session_id}}
        
        # ═══════════════════════════════════════════════════════
        # ✅ 构建合并的 system message（减少前缀碎片，优化 KV-cache）
        # ═══════════════════════════════════════════════════════
        system_parts = []
        
        # Part 1: 用户长期偏好（从数据库）
        if user_id:
            try:
                async with AsyncSessionLocal() as db_session:
                    from app.models import UserQueryPreference
                    result = await db_session.execute(
                        select(UserQueryPreference).where(
                            UserQueryPreference.user_id == uuid.UUID(user_id)
                        )
                    )
                    pref = result.scalar_one_or_none()
                    
                    if pref:
                        preference_context = []
                        if pref.intended_location:
                            preference_context.append(f"意向城市: {', '.join(pref.intended_location)}")
                        if pref.intended_industry:
                            preference_context.append(f"意向行业: {', '.join(pref.intended_industry)}")
                        if pref.intended_company_type:
                            preference_context.append(f"公司类型: {', '.join(pref.intended_company_type)}")
                        if pref.intended_position:
                            preference_context.append(f"意向职位: {', '.join(pref.intended_position)}")
                        
                        if preference_context:
                            system_parts.append(
                                "【用户长期偏好】\n" + "\n".join(preference_context)
                                + "\n\n注意：这些是用户的稳定偏好，但用户在当前对话中可能会调整。请优先参考会话级别的 Intent 文件。"
                            )
            except Exception as e:
                logger.warning("failed_to_load_user_preferences", error=str(e))
        
        # Part 2: 文件路径上下文
        if user_id:
            system_parts.append(
                f"【当前用户文件路径】\n"
                f"- 用户ID: {user_id}\n"
                f"- 会话ID: {session_id}\n"
                f"- Profile 文件: `profile.md` (已同步到当前 session 目录)\n"
                f"- Session 文件: `session.md`\n"
                f"- Intent 文件: `search_intent.json`\n\n"
                f"请根据以上路径读取和更新对应用户的记忆文件。"
            )
        
        # ═══════════════════════════════════════════════════════
        # ✅ 加载对话历史（当前用户消息已在 API 层保存到 DB）
        # ═══════════════════════════════════════════════════════
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
                    
                    # assistant 消息：拼接工具调用上下文摘要
                    if msg.role == "assistant" and msg.message_metadata:
                        tool_context = self._build_tool_context(msg.message_metadata)
                        if tool_context:
                            content += f"\n\n{tool_context}"
                    
                    history_messages.append({"role": msg.role, "content": content})
        except Exception as e:
            logger.warning("failed_to_load_conversation_history", error=str(e))
        
        # ═══════════════════════════════════════════════════════
        # ✅ 组装最终 messages（KV-cache 最优前缀稳定性）
        # ═══════════════════════════════════════════════════════
        messages = []
        
        # 1. 合并的 system message（最稳定前缀）
        if system_parts:
            messages.append({"role": "system", "content": "\n\n".join(system_parts)})
        
        # 2. 对话历史（append-only，前缀稳定）
        messages.extend(history_messages)
        
        # 3. 兆底：如果历史加载失败，至少要有当前消息
        if not any(m["role"] == "user" for m in messages):
            messages.append({"role": "user", "content": message})
        
        return agent, config, messages

    @staticmethod
    def _build_tool_context(metadata: dict) -> str | None:
        """从 message_metadata 构建工具调用上下文摘要，拼入历史 assistant 消息。
        
        让 Agent 在后续轮次能看到之前调用了哪些工具、搜索到了哪些岗位。
        """
        parts = []
        
        # 1. 搜索结果摘要（最高优先级）
        jobs_data = metadata.get("jobs")
        if jobs_data and isinstance(jobs_data, dict):
            jobs_list = jobs_data.get("jobs", [])
            if jobs_list:
                lines = [f"[上轮搜索结果 - {len(jobs_list)}个岗位]:"]
                for i, j in enumerate(jobs_list[:5]):
                    lines.append(
                        f"  {i+1}. {j.get('title', '')} @ {j.get('company', '')} "
                        f"({j.get('location', '')}, 匹配度{j.get('match_score', 0)}%)"
                    )
                parts.append("\n".join(lines))
        
        # 2. 其他工具调用摘要（不含 search_jobs，避免重复）
        tool_calls = metadata.get("tool_calls", [])
        other_calls = [tc for tc in tool_calls if tc.get("name") != "search_jobs"]
        if other_calls:
            call_lines = ["[上轮工具调用]:"]
            for tc in other_calls:
                name = tc.get("name", "unknown")
                args = tc.get("args", {})
                # 只展示关键参数，过滤内部 ID
                key_args = {
                    k: str(v)[:100]
                    for k, v in args.items()
                    if k not in ("user_id", "session_id")
                }
                call_lines.append(f"  - {name}({key_args})")
            parts.append("\n".join(call_lines))
        
        return "\n\n".join(parts) if parts else None

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
            
            # ✅ 工具中文描述映射（用于前端卡片显示）
            TOOL_DISPLAY_NAMES = {
                "search_jobs": "正在搜索匹配岗位",
                "read_file": "正在读取记忆文件",
                "write_file": "正在更新记忆文件",
                "edit_file": "正在更新记忆文件",
                "get_user_profile": "正在查阅用户偏好",
                "ls": "正在浏览文件目录",
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
                    chunk = event.get("data", {}).get("chunk")
                    # ✅ 过滤空 token：LLM 生成 tool_calls 时 chunk.content 为空字符串
                    if chunk and chunk.content:
                        full_response += chunk.content
                        yield {"type": "token", "data": chunk.content}
                
                elif event_type == "on_tool_start":
                    # ✅ 收集工具调用参数 + 推送 tool_start 事件
                    tool_name = event.get("name", "")
                    tool_input = event.get("data", {}).get("input", {})
                    tool_calls_log.append({"name": tool_name, "args": tool_input})
                    display = TOOL_DISPLAY_NAMES.get(tool_name, f"正在调用 {tool_name}")
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
            
            # ✅ yield 工具调用数据供 API 层持久化
            if tool_calls_log:
                yield {"type": "tool_calls", "data": tool_calls_log}
            if tool_results_log:
                yield {"type": "tool_results", "data": tool_results_log}
            
            yield {"type": "final_response", "data": full_response}
            
            # ✅ 长期偏好更新：检测 Agent 是否更新了 profile.md
            if user_id:
                try:
                    updated = await self._sync_profile_from_session(user_id, session_id)
                    if updated:
                        logger.info(
                            "long_term_preferences_updated",
                            session_id=session_id,
                            user_id=user_id,
                            message="Agent updated long-term preferences, synced to all sessions"
                        )
                except Exception as e:
                    logger.warning(
                        "profile_sync_back_failed",
                        session_id=session_id,
                        user_id=user_id,
                        error=str(e)
                    )
        
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
            
            logger.info(
                "chat_stream_completed",
                session_id=session_id,
                response_length=len(response_content)
            )
            
            # ✅ 长期偏好更新：检测 Agent 是否更新了 profile.md，如果有则同步回 user 目录
            if user_id:
                try:
                    updated = await self._sync_profile_from_session(user_id, session_id)
                    if updated:
                        logger.info(
                            "long_term_preferences_updated",
                            session_id=session_id,
                            user_id=user_id,
                            message="Agent updated long-term preferences, synced to user directory"
                        )
                except Exception as e:
                    logger.warning(
                        "profile_sync_back_failed",
                        session_id=session_id,
                        user_id=user_id,
                        error=str(e)
                    )
                    # 不阻断对话，继续返回响应
            
            return response_content
        except Exception as e:
            logger.error(
                "chat_stream_failed",
                session_id=session_id,
                error=str(e)
            )
            raise
