from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.agents.conversation_agent import ConversationAgent
from app.schemas import ChatMessageRequest, ChatMessageResponse, ChatSessionResponse
from app.api.dependencies import get_current_user
from app.models import User
import uuid

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


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: str,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user)
):
    """Send a message and get AI response"""
    try:
        response = await conversation_agent.chat(
            message=request.message,
            session_id=session_id,
            user_id=str(current_user.id)
        )
        
        return ChatMessageResponse(
            reply=response,
            session_id=uuid.UUID(session_id)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
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
