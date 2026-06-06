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
                        assistant_msg = ChatMessage(
                            session_id=_session_id,
                            role="assistant",
                            content=full_response,
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
