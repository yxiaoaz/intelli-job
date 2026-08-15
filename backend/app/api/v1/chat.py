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
from app.utils.logger import get_logger

logger = get_logger()

router = APIRouter()


def _parse_session_id(session_id: str) -> uuid.UUID:
    """Parse session_id path param into UUID, raising 422 on invalid format"""
    try:
        return uuid.UUID(session_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="无效的会话 ID")

# Initialize conversation agent (singleton)
conversation_agent = ConversationAgent()


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session"""
    session = ChatSession(user_id=current_user.id, title="新对话")
    db.add(session)
    await db.flush()
    await db.refresh(session)

    logger.info(
        "chat_session_created",
        session_id=str(session.id),
        user_id=str(current_user.id),
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
    session_uuid = _parse_session_id(session_id)
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
            session_id=session_uuid,
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

    _session_id = _parse_session_id(session_id)
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

                    # 3.5 reconcile: markdown -> DB 兜底同步
                    try:
                        from app.memory.reconcile import chat_end_reconcile
                        from app.memory.service import MemoryService
                        from app.services.intent_file_service import IntentFileService
                        _mem_svc = MemoryService(db, base_dir=IntentFileService().base_dir)
                        _md_path = str(_mem_svc.session_markdown_path(_user_id, session_id))
                        await chat_end_reconcile(db, _user_id, session_id, _md_path)
                    except Exception as reconcile_err:
                        logger.warning("chat_end_reconcile_skipped", error=str(reconcile_err))
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
        select(ChatSession).where(ChatSession.id == _parse_session_id(session_id))
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
        select(ChatSession).where(ChatSession.id == _parse_session_id(session_id))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    # Fetch messages
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == _parse_session_id(session_id))
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
        select(ChatSession).where(ChatSession.id == _parse_session_id(session_id))
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


@router.patch("/sessions/{session_id}")
async def update_session_title(
    session_id: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新会话标题（用于自动生成标题）"""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == _parse_session_id(session_id))
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
