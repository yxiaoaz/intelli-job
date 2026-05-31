from deepagents import create_deep_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.services.llm_service import LLMService
from app.services.job_matching_service import JobMatchingService
from app.repositories.user_repo import UserRepository
from app.repositories.job_repo import BookmarkRepository
from app.utils.logger import get_logger
import uuid
import json

logger = get_logger()


class ConversationAgent:
    """DeepAgent for conversational job assistance using deepagents framework"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.job_matching_service = JobMatchingService()
        self.agent = self._create_agent()
    
    def _create_agent(self, checkpointer=None):
        """Create the Deep Agent using deepagents.create_deep_agent
        
        Args:
            checkpointer: Optional LangGraph checkpointer for persistence
        """
        
        # Define tools
        @tool
        async def search_jobs(query: str, filters: dict = {}) -> str:
            """Search for matching jobs based on query and filters.
            
            Args:
                query: Job search query (e.g., "产品经理 北京")
                filters: Optional filters like recruitment_type
            
            Returns:
                Formatted string of job results
            """
            try:
                results = await self.job_matching_service.match_jobs(
                    user_query_preference={"keywords": query},
                    user_resume_profile={},
                    hard_filters=filters,
                    top_k=10
                )
                
                if not results:
                    return "没有找到匹配的职位"
                
                formatted = []
                for item in results[:5]:  # Top 5 results
                    job = item["job_item"]
                    formatted.append(
                        f"- {job.job_title} at {job.company_name}\n"
                        f"  地点: {job.location}, 薪资: {job.salary}\n"
                        f"  要求: {job.min_academic_qualification.value}"
                    )
                
                return "\n".join(formatted)
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
                # This would fetch from database in real implementation
                return f"用户ID: {user_id}\n技能: Python, SQL, 数据分析\n偏好: 北京, 产品经理"
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
                
                response = await llm.ainvoke(prompt)
                return response.content
            except Exception as e:
                logger.error("analyze_job_match_tool_failed", error=str(e))
                return f"分析失败: {str(e)}"
        
        tools = [search_jobs, get_user_profile, analyze_job_match]
        
        # System prompt for the agent
        system_prompt = (
            "你是一个专业的求职助手。你的目标是帮助用户找到理想的工作。\n\n"
            "你可以执行以下操作：\n"
            "1. 分析用户的简历和求职意向\n"
            "2. 搜索并推荐匹配的职位（使用 search_jobs 工具）\n"
            "3. 分析职位匹配度（使用 analyze_job_match 工具）\n"
            "4. 提供面试建议和职业规划指导\n\n"
            "当用户询问职位时，请调用 search_jobs 工具进行搜索。\n"
            "如果信息不足，请主动询问用户。\n"
            "回答要简洁、专业、有帮助性。"
        )
        
        # Create deep agent using deepagents framework
        agent = create_deep_agent(
            model=self.llm_service.chat_model,
            tools=tools,
            system_prompt=system_prompt,
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
        config = {"configurable": {"thread_id": session_id}}
        
        # Add user context if provided
        messages = [{"role": "user", "content": message}]
        
        if user_id:
            # Could add user profile context here
            pass
        
        try:
            result = await self.agent.ainvoke(
                {"messages": messages},
                config=config
            )
            
            # Extract the last assistant message
            response = result["messages"][-1].content
            logger.info("chat_response_generated", session_id=session_id)
            
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
        config = {"configurable": {"thread_id": session_id}}
        
        # Build messages with history (handled by checkpointer automatically)
        messages = [{"role": "user", "content": message}]
        
        try:
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
                    yield {
                        "type": "tool_start",
                        "data": {"tool": tool_name}
                    }
                
                elif event_type == "on_tool_end":
                    # Tool execution completed
                    tool_name = event.get("name", "unknown")
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
                            yield {
                                "type": "final_response",
                                "data": final_message.content
                            }
                
        except Exception as e:
            logger.error("chat_stream_failed", session_id=session_id, error=str(e))
            yield {
                "type": "error",
                "data": f"抱歉，我遇到了一些问题：{str(e)}"
            }
