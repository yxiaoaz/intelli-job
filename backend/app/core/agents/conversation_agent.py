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

logger = get_logger()


class ConversationAgent:
    """DeepAgent for conversational job assistance using deepagents framework"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.job_matching_service = JobMatchingService()
        self.intent_file_service = IntentFileService()
        self.agent = self._create_agent()
    
    def _create_agent(self, checkpointer=None):
        """Create the Deep Agent using deepagents.create_deep_agent
        
        Args:
            checkpointer: Optional LangGraph checkpointer for persistence
        """
        
        # Define tools
        @tool
        async def search_jobs(
            query: str,
            filters: dict = {},
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
                    profile_info = [f"用户邮箱: {user.email}"]
                    
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
            
            "【Intent 文件管理】（重要）\n"
            "你可以自主读写用户的 Intent 文件，用于持久化求职偏好：\n"
            "- **文件位置**: `user-{user_id}/session-{thread_id}.md`\n"
            "- **文件格式**: Markdown，包含 Metadata、Preferences、Reasoning 三个部分\n"
            "- **读取时机**: \n"
            "  1. 对话开始时，检查是否有现有 Intent 文件\n"
            "  2. **调用 search_jobs 之前**，先读取 Intent 了解用户偏好\n"
            "- **更新时机**: 当用户表达新的求职偏好时，及时更新文件\n"
            "- **示例操作**:\n"
            "  ```\n"
            "  # 读取现有 Intent\n"
            "  read_file('user-abc123/session-thread-xyz.md')\n"
            "  \n"
            "  # 根据 Intent 构造查询\n"
            "  # 假设 Intent 中 preferred_city=['深圳'], preferred_job_titles=['产品经理']\n"
            "  search_jobs(query='产品经理 深圳', session_id='thread-xyz', user_id='abc123')\n"
            "  \n"
            "  # 更新 Intent（先读取，修改后写入）\n"
            "  write_file('user-abc123/session-thread-xyz.md', '新内容...')\n"
            "  ```\n"
            "- **注意事项**:\n"
            "  - 保持文件格式一致（使用 key: value 格式）\n"
            "  - 列表字段用逗号分隔（如：preferred_city: 深圳, 北京）\n"
            "  - 每次更新时保留原有的 reasoning，追加新的推理\n"
            "  - **search_jobs 工具不再自动加载 Intent，你需要在 query 参数中包含关键信息**\n\n"
            
            "【重要规则】\n"
            "- 不要每轮都问问题！如果用户说了岗位关键词，直接搜索\n"
            "- 默认会结合用户的简历信息进行精准匹配\n"
            "- 如果用户还没上传简历，主动鼓励用户上传\n"
            "- 搜索结果最多展示5个岗位，简洁解读\n"
            "- 如果用户切换求职方向（如从'算法'转到'产品'），重新搜索\n\n"
            
            "【处理 search_jobs 返回结果】（最高优先级规则）\n"
            "当调用 search_jobs 工具后，工具会返回一个 JSON 字符串，格式为：\n"
            '{"type":"job_search_results","count":N,"jobs":[{...}]}\n\n'
            "**你的唯一任务：**\n"
            "1. 阅读 JSON 中的岗位信息，理解内容\n"
            "2. 用1-2句话向用户简要介绍（例如：'找到X个岗位，匹配度Y-Z%'）\n"
            "3. **立即在下一行输出完整 JSON**，格式必须严格如下：\n"
            "   ```json\n"
            "   {工具的完整返回值，逐字复制，不做任何修改}\n"
            "   ```\n\n"
            "**绝对禁止行为（违反将导致系统错误）：**\n"
            "❌ 绝对不要用文本/列表/编号格式展示岗位\n"
            "❌ 绝对不要自己重新生成、改写、格式化 JSON\n"
            "❌ 绝对不要删除、修改、截断任何字段或值\n"
            "❌ 绝对不要添加额外的说明文字在 JSON 代码块中\n"
            "❌ 绝对不要将 JSON 分散到多处\n\n"
            "**正确输出格式示例：**\n"
            "```\n"
            "我为你找到了5个产品经理岗位，匹配度在70-90%之间。\n"
            "\n"
            "```json\n"
            '{"type":"job_search_results","count":5,"jobs":[{"id":"uuid-1","title":"产品经理","company":"快手","location":"北京","salary_min":null,"salary_max":null,"salary_currency":"CNY","description":"...","truncated_description":"...","requirements":[],"url":"...","source":"shixiseng","match_score":85.5,"match_analysis":"匹配度 85.5%"}]}\n'
            "```\n"
            "```\n\n"
            "**错误示例（严禁）：**\n"
            "```\n"
            "我找到了以下岗位：\n"
            "1. 产品经理 - 快手（北京） - 匹配度85%\n"
            "2. ...\n"
            "```\n"
            "（上面这种文本列表格式是绝对禁止的！必须输出 JSON 代码块！）\n"
            "```\n\n"
            
            "【对话风格】\n"
            "- 简洁、专业、有同理心\n"
            "- 避免机械式提问，像真人顾问一样自然交流\n"
            "- 主动告知用户：'我已将你的简历纳入搜索条件'"
        )
        
        # Create deep agent using deepagents framework
        # Pass custom backend to enable file system access for Intent management
        filesystem_backend = FilesystemBackend(
            root_dir=self.intent_file_service.base_dir,
            max_file_size_mb=10,  # Limit file size to 10MB
            virtual_mode=True  # Enable virtual path semantics for security
        )
        
        agent = create_deep_agent(
            model=self.llm_service.chat_model,
            tools=tools,
            system_prompt=system_prompt,
            backend=filesystem_backend,  # Pass backend directly, not as middleware
            checkpointer=checkpointer,  # Enable persistence if checkpointer provided
        )
        
        return agent
    
    async def chat(
        self,
        message: str,
        session_id: str,
        user_id: str | None = None
    ) -> str:
        """
        Process a chat message and return response
        
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
        
        config = {"configurable": {"thread_id": session_id}}
        
        # Add user context if provided
        messages = [{"role": "user", "content": message}]
        
        if user_id:
            # Could add user profile context here
            pass
        
        try:
            logger.info("invoking_conversation_agent")
            
            result = await self.agent.ainvoke(
                {"messages": messages},
                config=config
            )
            
            # Extract the last assistant message
            response = result["messages"][-1].content
            
            logger.info(
                "chat_response_generated",
                session_id=session_id,
                response_length=len(response) if isinstance(response, str) else 0,
                response_preview=response[:200] if isinstance(response, str) else ""
            )
            
            return response
        except Exception as e:
            logger.error("chat_failed", session_id=session_id, error=str(e))
            return f"抱歉，我遇到了一些问题：{str(e)}"
    
    async def chat_stream(
        self,
        message: str,
        session_id: str,
        user_id: str | None = None
    ):
        """
        Process a chat message with streaming output (SSE)
        
        Args:
            message: User's message
            session_id: Unique session ID for conversation history
            user_id: Optional user ID for personalization
            
        Yields:
            Dict with event data for SSE streaming
        """
        logger.info(
            "chat_stream_request_received",
            session_id=session_id,
            user_id=user_id,
            message_length=len(message),
            message_preview=message[:100]
        )
        
        config = {"configurable": {"thread_id": session_id}}
        
        # Build messages with history (handled by checkpointer automatically)
        messages = [{"role": "user", "content": message}]
        
        try:
            logger.info("starting_chat_stream")
            
            # Use astream_events for fine-grained streaming
            async for event in self.agent.astream_events(
                {"messages": messages},
                config=config,
                version="v2"  # Use v2 format for cleaner output
            ):
                # Extract relevant information from event
                event_type = event.get("event")
                
                # Filter and format events for frontend
                if event_type == "on_chat_model_stream":
                    # LLM token generation
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, 'content'):
                        yield {
                            "type": "token",
                            "data": chunk.content
                        }
                
                elif event_type == "on_tool_start":
                    # Tool execution started
                    tool_name = event.get("name", "unknown")
                    logger.info(f"tool_execution_started: {tool_name}")
                    yield {
                        "type": "tool_start",
                        "data": {"tool": tool_name}
                    }
                
                elif event_type == "on_tool_end":
                    # Tool execution completed
                    tool_name = event.get("name", "unknown")
                    logger.info(f"tool_execution_completed: {tool_name}")
                    yield {
                        "type": "tool_end",
                        "data": {"tool": tool_name}
                    }
                
                elif event_type == "on_chain_end":
                    # Agent finished processing
                    output = event.get("data", {}).get("output")
                    if output and "messages" in output:
                        final_message = output["messages"][-1]
                        if hasattr(final_message, 'content'):
                            content = final_message.content
                            
                            # ✅ 第三层防护:验证输出格式
                            import re
                            has_json_block = "```json" in content and '"jobs"' in content
                            has_text_list = bool(re.search(r'^\d+\.\s+', content, re.MULTILINE))
                            
                            # 记录格式检查结果
                            logger.info(
                                "chat_response_format_check",
                                session_id=session_id,
                                has_json_block=has_json_block,
                                has_text_list=has_text_list,
                                response_length=len(content)
                            )
                            
                            # 如果检测到格式错误,添加警告(不影响正常输出)
                            if has_text_list and not has_json_block:
                                logger.warning(
                                    "llm_output_format_violation",
                                    session_id=session_id,
                                    message="LLM 输出了文本列表格式而非 JSON"
                                )
                                # 可选:在末尾添加提示(不推荐,会影响用户体验)
                                # content += "\n\n️ 系统提示:岗位数据格式异常,请重试"
                            
                            logger.info(
                                "chat_stream_completed",
                                session_id=session_id,
                                response_length=len(content)
                            )
                            yield {
                                "type": "final_response",
                                "data": content
                            }
                
        except Exception as e:
            logger.error("chat_stream_failed", session_id=session_id, error=str(e))
            yield {
                "type": "error",
                "data": f"抱歉，我遇到了一些问题：{str(e)}"
            }
