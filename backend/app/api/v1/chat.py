import asyncio
import uuid
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, AsyncSessionLocal
from app.config import get_settings
from app.core.agents.conversation_agent import ConversationAgent
from app.core.rate_limiter import ai_limit
from app.core.redis import get_redis, incr_with_ttl, safe_redis
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
settings = get_settings()

router = APIRouter()


def _parse_session_id(session_id: str) -> uuid.UUID:
    """Parse session_id path param into UUID, raising 422 on invalid format"""
    try:
        return uuid.UUID(session_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="无效的会话 ID")


async def _get_owned_session(
    session_id: uuid.UUID, current_user: User, db: AsyncSession
) -> ChatSession:
    """归属校验：不存在或非本人 → 404（不返回 403，避免存在性泄露）。

    IDOR 修复：send_message / send_message_stream 原先只做 UUID 格式解析，
    任意登录用户可往他人会话注入消息。见 openspec/changes/api-abuse-protection/design.md 第 2 节。
    """
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


def _quota_key(user_id) -> str:
    """每日配额 key：chat_quota:{user_id}:{YYYYMMDD}，按日自然滚动（服务器本地时区）"""
    return f"chat_quota:{user_id}:{datetime.now().strftime('%Y%m%d')}"


async def _check_daily_quota(user_id) -> bool:
    """每日消息配额检查。返回 True=放行；超限或 Redis 降级语义见 design.md 7.1。

    Redis 不可用时 safe_redis 返回 None → 放行（防护失效优于业务不可用）。
    """
    used = await safe_redis(lambda: get_redis().get(_quota_key(user_id)))
    if used is not None and int(used) >= settings.CHAT_DAILY_MESSAGE_LIMIT:
        return False
    return True


async def _incr_daily_quota(user_id) -> None:
    """用户消息落库成功后计数（原子建键带 TTL，失败请求不消耗配额）"""
    await incr_with_ttl(_quota_key(user_id), 86400)

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
@ai_limit
async def send_message(
    request: Request,          # slowapi 硬性要求（分档限流）
    session_id: str,
    message_request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and get AI response (non-streaming)

    DEPRECATED: Use /stream endpoint for better UX
    This endpoint is kept for backward compatibility.
    """
    session_uuid = _parse_session_id(session_id)
    await _get_owned_session(session_uuid, current_user, db)

    # 每日配额：超限拒绝（非流式 429 + 友好文案）
    if not await _check_daily_quota(current_user.id):
        raise HTTPException(status_code=429, detail="今日对话次数已用完，明天再来吧～")

    try:
        full_response = ""
        async for event in conversation_agent.chat_stream(
            message=message_request.message,
            session_id=session_id,
            user_id=str(current_user.id),
        ):
            if event["type"] == "token":
                full_response += event["data"]
            elif event["type"] == "final_response":
                full_response = event["data"]
                break

        # 每日配额计数：与 stream 端点同语义，仅成功响应消耗配额
        await _incr_daily_quota(current_user.id)

        return ChatMessageResponse(
            reply=full_response,
            session_id=session_uuid,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/sessions/{session_id}/messages/stream")
@ai_limit
async def send_message_stream(
    request: Request,          # slowapi 硬性要求（分档限流）
    session_id: str,
    message_request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get AI response with SSE streaming"""

    _session_id = _parse_session_id(session_id)
    _user_id = current_user.id
    _message = message_request.message

    # 归属校验必须在 event_generator 之外：生成器体内抛出的 HTTPException
    # 不会转成正常 HTTP 响应（会变成 SSE 流中的 error）
    await _get_owned_session(_session_id, current_user, db)

    # 每日配额：超限时复用 llm-service-resilience 已落地的降级帧
    # （token + final_response 结构不变，前端零改动），不触达 Agent
    if not await _check_daily_quota(_user_id):
        quota_text = "今日对话次数已用完，明天再来吧～"

        async def quota_generator():
            degraded_event = {"type": "token", "data": quota_text}
            yield f"data: {json.dumps(degraded_event, ensure_ascii=False)}\n\n"
            final_event = {"type": "final_response", "data": quota_text}
            yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            quota_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

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

                # 1.2 每日配额计数：放在用户消息落库成功后（失败请求不消耗配额）
                await _incr_daily_quota(_user_id)

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
                # LLM 链路异常：不再发裸 error 帧，而是发用户友好的降级文案
                # （前端对正常 content/token 帧零改动；error 帧仅保留给非 LLM 类确定性错误）
                logger.error(
                    "chat_stream_error",
                    session_id=str(_session_id),
                    error=str(e),
                )
                degraded_text = "AI 服务暂时不可用，请稍后重试。你也可以先试试职位搜索～"
                # 部分回复已输出时追加，否则整体替换，保证降级消息走持久化逻辑
                full_response = (
                    full_response + degraded_text if full_response else degraded_text
                )
                degraded_event = {"type": "token", "data": degraded_text}
                yield f"data: {json.dumps(degraded_event, ensure_ascii=False)}\n\n"
                final_event = {"type": "final_response", "data": full_response}
                yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"
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
    return await _get_owned_session(_parse_session_id(session_id), current_user, db)


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
    session_uuid = _parse_session_id(session_id)

    # Verify session ownership
    await _get_owned_session(session_uuid, current_user, db)

    # Fetch messages
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_uuid)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    # ✅ DB 中 created_at 为 naive UTC，补 UTC tzinfo 让响应序列化为
    # 'Z' 结尾的 ISO 时间，浏览器 new Date() 才能按 UTC 解析，
    # 否则历史消息时间显示会差时区偏移
    return [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "message_metadata": m.message_metadata,
            "created_at": m.created_at.replace(tzinfo=timezone.utc) if m.created_at else None,
        }
        for m in messages
    ]


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a chat session and all its messages"""
    session = await _get_owned_session(_parse_session_id(session_id), current_user, db)

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
    session = await _get_owned_session(_parse_session_id(session_id), current_user, db)

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
