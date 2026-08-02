import asyncio
import uuid
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, AsyncSessionLocal
from app.core.agents.conversation_agent import ConversationAgent
from app.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionResponse,
    ChatMessageItemResponse,
)
from app.api.dependencies import get_current_user
from app.models import User, ChatSession, ChatMessage
from app.repositories.session_intent_repo import SessionIntentRepository
from app.services.intent_file_service import IntentFileService
from app.utils.logger import get_logger

logger = get_logger()

router = APIRouter()

# Initialize conversation agent (singleton)
conversation_agent = ConversationAgent()


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session and initialize memory files"""
    session = ChatSession(user_id=current_user.id, title="新对话")
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # Initialize Agent Memory Files
    intent_service = IntentFileService()
    user_id_str = str(current_user.id)
    session_id_str = str(session.id)
    
    # 1. Initialize session.md with default state
    initial_state = {
        "thread_id": session_id_str,
        "user_id": user_id_str,
        "current_goal": "等待用户输入求职意向",
        "confirmed_preferences": [],
        "open_questions": ["您想找什么类型的岗位？", "您期望的工作地点在哪里？"],
        "next_action": "等待用户输入"
    }
    intent_service.save_intent(user_id_str, session_id_str, initial_state)
    
    # 2. Initialize search_intent.json - 尝试从用户简历中提取初始意图
    initial_intent = {
        "target_roles": [],
        "locations": [],
        "salary": None,
        "experience": None,
        "filters": {}
    }
    
    # 尝试从用户的激活简历中提取技能等信息
    try:
        from app.models import Resume
        from sqlalchemy import select
        result = await db.execute(
            select(Resume).where(
                Resume.user_id == current_user.id,
                Resume.active_status == True
            ).limit(1)
        )
        active_resume = result.scalar_one_or_none()
        
        if active_resume and active_resume.extracted_content:
            resume_data = active_resume.extracted_content
            
            # 提取技能
            skills = resume_data.get('skills', [])
            if skills and isinstance(skills, list):
                initial_intent['filters']['skills'] = ', '.join(skills[:10])
            
            # 提取当前职位
            work_exp = resume_data.get('work_experience', [])
            if work_exp and isinstance(work_exp, list) and len(work_exp) > 0:
                latest_job = work_exp[0]
                if isinstance(latest_job, dict):
                    title = latest_job.get('title') or latest_job.get('position')
                    if title:
                        initial_intent['filters']['current_title'] = title
            
            # 提取学历
            education = resume_data.get('education', [])
            if education and isinstance(education, list) and len(education) > 0:
                highest_edu = education[0]
                if isinstance(highest_edu, dict):
                    degree = highest_edu.get('degree')
                    if degree:
                        initial_intent['filters']['education_level'] = degree
            
            logger.info(
                "initial_intent_from_resume",
                session_id=session_id_str,
                filters=initial_intent['filters']
            )
    except Exception as e:
        logger.warning("failed_to_extract_initial_intent", error=str(e))
    
    intent_service.update_search_intent(user_id_str, session_id_str, initial_intent)

    logger.info(
        "chat_session_created",
        session_id=session_id_str,
        user_id=user_id_str,
    )
    return session


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    deprecated=True,
)
async def send_message(
    session_id: str,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Send a message and get AI response (non-streaming)

    DEPRECATED: Use /stream endpoint for better UX
    This endpoint is kept for backward compatibility.
    """
    try:
        full_response = ""
        async for event in conversation_agent.chat_stream(
            message=request.message,
            session_id=session_id,
            user_id=str(current_user.id),
        ):
            if event["type"] == "token":
                full_response += event["data"]
            elif event["type"] == "final_response":
                full_response = event["data"]
                break

        return ChatMessageResponse(
            reply=full_response,
            session_id=uuid.UUID(session_id),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: str,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a message and get AI response with SSE streaming"""

    _session_id = uuid.UUID(session_id)
    _user_id = current_user.id
    _message = request.message

    async def event_generator():
        full_response = ""
        pending_jobs = None  # structured payload intercepted from search_jobs tool
        pending_tool_calls = None   # all tool call args
        pending_tool_results = None  # all tool call results
        async with AsyncSessionLocal() as db:
            try:
                # 1. Save user message immediately
                user_msg = ChatMessage(
                    session_id=_session_id,
                    role="user",
                    content=_message,
                )
                db.add(user_msg)
                await db.flush()

                logger.info(
                    "chat_user_message_saved",
                    session_id=str(_session_id),
                    message_id=str(user_msg.id),
                )
                
                # 1.5 Auto-generate session title from first user message
                result = await db.execute(
                    select(ChatSession).where(ChatSession.id == _session_id)
                )
                session_obj = result.scalar_one_or_none()
                if session_obj and session_obj.title == "新对话":
                    # Extract first 20 chars as title
                    auto_title = _message.strip()[:20]
                    if len(_message.strip()) > 20:
                        auto_title += "..."
                    session_obj.title = auto_title
                    logger.info(
                        "chat_session_auto_titled",
                        session_id=str(_session_id),
                        title=auto_title,
                    )

                # 2. Stream LLM response
                async for event in conversation_agent.chat_stream(
                    message=_message,
                    session_id=session_id,
                    user_id=str(_user_id),
                ):
                    if event["type"] == "token":
                        full_response += event["data"]
                    elif event["type"] == "final_response":
                        full_response = event["data"]
                    elif event["type"] == "job_results":
                        # Capture for metadata persistence; event is still
                        # forwarded to the frontend via the yield below.
                        pending_jobs = event.get("data")
                    elif event["type"] == "tool_calls":
                        pending_tool_calls = event.get("data")
                    elif event["type"] == "tool_results":
                        pending_tool_results = event.get("data")

                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            except asyncio.CancelledError:
                logger.info(
                    "chat_stream_cancelled_by_client",
                    session_id=str(_session_id),
                    partial_length=len(full_response),
                )
                raise
            except Exception as e:
                logger.error(
                    "chat_stream_error",
                    session_id=str(_session_id),
                    error=str(e),
                )
                error_event = {"type": "error", "data": str(e)}
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            finally:
                # 3. Persist assistant response (even on disconnect)
                try:
                    if full_response:
                        # Build metadata with all tool data
                        metadata = {}
                        if pending_jobs:
                            metadata["jobs"] = pending_jobs
                        if pending_tool_calls:
                            metadata["tool_calls"] = pending_tool_calls
                        if pending_tool_results:
                            metadata["tool_results"] = pending_tool_results
                        
                        assistant_msg = ChatMessage(
                            session_id=_session_id,
                            role="assistant",
                            content=full_response,
                            message_metadata=metadata if metadata else None,
                        )
                        db.add(assistant_msg)

                        logger.info(
                            "chat_assistant_message_saved",
                            session_id=str(_session_id),
                            response_length=len(full_response),
                        )

                    # 4. Update session timestamp
                    result = await db.execute(
                        select(ChatSession).where(ChatSession.id == _session_id)
                    )
                    session_obj = result.scalar_one_or_none()
                    if session_obj:
                        session_obj.updated_at = datetime.utcnow()

                    await db.commit()
                except Exception as commit_err:
                    logger.error(
                        "chat_persist_commit_failed",
                        session_id=str(_session_id),
                        error=str(commit_err),
                    )
                    await db.rollback()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's chat sessions, ordered by most recent first"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return sessions


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get specific chat session details"""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    return session


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageItemResponse],
)
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all messages for a session, ordered by creation time"""
    # Verify session ownership
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    # Fetch messages
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == uuid.UUID(session_id))
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return messages


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a chat session and all its messages"""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除该会话")

    # Cascade delete will remove all messages (defined in model with cascade="all, delete-orphan")
    await db.delete(session)
    await db.commit()

    logger.info(
        "chat_session_deleted",
        session_id=session_id,
        user_id=str(current_user.id),
    )
    return {"status": "success"}


# === Session Intent APIs ===

@router.get("/sessions/{session_id}/intent")
async def get_session_intent(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前会话的用户意图记忆 (从文件读取)"""
    intent_service = IntentFileService()
    user_id_str = str(current_user.id)
    
    # 优先从 search_intent.json 读取
    session_dir = intent_service.get_session_dir(user_id_str, session_id)
    intent_path = session_dir / "search_intent.json"
    
    if intent_path.exists():
        try:
            import json
            with open(intent_path, 'r', encoding='utf-8') as f:
                intent_data = json.load(f)
            return {"thread_id": session_id, "intent": intent_data}
        except Exception as e:
            logger.error("failed_to_read_intent_file", error=str(e))
    
    # 如果文件不存在，返回空模板
    return {
        "thread_id": session_id,
        "intent": {
            "target_roles": [],
            "locations": [],
            "salary": None,
            "experience": None,
            "filters": {}
        }
    }


from pydantic import BaseModel
from typing import Optional, List

class IntentUpdateRequest(BaseModel):
    """Intent 更新请求"""
    preferred_city: Optional[List[str]] = None
    preferred_job_titles: Optional[List[str]] = None
    salary_expectation: Optional[dict] = None
    skills: Optional[List[str]] = None
    include_resume_in_search: Optional[bool] = None
    search_direction: Optional[str] = None


@router.put("/sessions/{session_id}/intent")
async def update_session_intent(
    session_id: str,
    request: dict, # 接收任意字典以适配 SearchIntent 结构
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户手动调整求职意向（通过前端 UI），同步更新 search_intent.json"""
    intent_service = IntentFileService()
    user_id_str = str(current_user.id)
    
    # 过滤掉不需要的字段，只保留 SearchIntent 相关的
    # 支持两种字段命名方式：前端可能发送 locations/target_roles，也可能发送 preferred_city/preferred_job_titles
    updates = {
        "target_roles": request.get("target_roles") or request.get("preferred_job_titles", []),
        "locations": request.get("locations") or request.get("preferred_city", []),
        "salary": request.get("salary") or request.get("salary_expectation"),
        "experience": request.get("experience"),
        "filters": request.get("filters", {})
    }
    
    intent_service.update_search_intent(user_id_str, session_id, updates)
    
    # 读取更新后的完整意图数据并返回
    session_dir = intent_service.get_session_dir(user_id_str, session_id)
    intent_path = session_dir / "search_intent.json"
    
    if intent_path.exists():
        try:
            import json
            with open(intent_path, 'r', encoding='utf-8') as f:
                intent_data = json.load(f)
            return {"thread_id": session_id, "intent": intent_data}
        except Exception as e:
            logger.error("failed_to_read_updated_intent", error=str(e))
    
    # 如果读取失败，返回更新后的数据
    return {
        "thread_id": session_id,
        "intent": updates
    }


@router.patch("/sessions/{session_id}")
async def update_session_title(
    session_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新会话标题（用于自动生成标题）"""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    # 更新标题
    new_title = request.get("title")
    if new_title:
        session.title = new_title
        await db.commit()
        await db.refresh(session)
        
        logger.info(
            "chat_session_title_updated",
            session_id=session_id,
            title=new_title,
        )

    return session
