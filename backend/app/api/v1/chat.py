from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.agents.conversation_agent import ConversationAgent
from app.schemas import ChatMessageRequest, ChatMessageResponse, ChatSessionResponse
from app.api.dependencies import get_current_user
from app.models import User
import uuid
import json

router = APIRouter()

# Initialize conversation agent (singleton)
conversation_agent = ConversationAgent()


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat session"""
    # In real implementation, save to database
    session_id = uuid.uuid4()
    
    return ChatSessionResponse(
        id=session_id,
        title="新对话",
        created_at=None,
        updated_at=None
    )


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse, deprecated=True)
async def send_message(
    session_id: str,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Send a message and get AI response (non-streaming)
    
    ⚠️ DEPRECATED: Use /stream endpoint for better UX
    This endpoint is kept for backward compatibility.
    """
    try:
        # Collect all tokens from stream
        full_response = ""
        async for event in conversation_agent.chat_stream(
            message=request.message,
            session_id=session_id,
            user_id=str(current_user.id)
        ):
            if event["type"] == "token":
                full_response += event["data"]
            elif event["type"] == "final_response":
                full_response = event["data"]
                break
        
        return ChatMessageResponse(
            reply=full_response,
            session_id=uuid.UUID(session_id)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: str,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user)
):
    """Send a message and get AI response with SSE streaming"""
    
    async def event_generator():
        try:
            async for event in conversation_agent.chat_stream(
                message=request.message,
                session_id=session_id,
                user_id=str(current_user.id)
            ):
                # Format as SSE event
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "data": str(e)
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's chat sessions"""
    # In real implementation, fetch from database
    return []


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get specific chat session details"""
    return ChatSessionResponse(
        id=uuid.UUID(session_id),
        title="对话历史",
        created_at=None,
        updated_at=None
    )
