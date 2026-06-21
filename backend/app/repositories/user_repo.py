from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User
from app.utils.security import get_password_hash
import uuid


class UserRepository:
    """Repository for User operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get user by ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> User | None:
        """Get user by email"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def create(self, email: str, password: str, security_question: str | None = None, security_answer: str | None = None) -> User:
        """Create a new user"""
        hashed_password = get_password_hash(password)
        security_answer_hash = get_password_hash(security_answer) if security_answer else None
        user = User(
            email=email,
            hashed_password=hashed_password,
            security_question=security_question,
            security_answer_hash=security_answer_hash,
        )
        self.session.add(user)
        await self.session.flush()
        return user
    
    async def update(self, user: User) -> User:
        """Update user"""
        await self.session.flush()
        return user
    
    async def update_password(self, user_id: uuid.UUID, new_password: str) -> User:
        """Update user password"""
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        user.hashed_password = get_password_hash(new_password)
        await self.session.flush()
        return user
    
    async def set_security_question(self, user_id: uuid.UUID, question: str, answer: str) -> User:
        """Set or update security question and answer"""
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        user.security_question = question
        user.security_answer_hash = get_password_hash(answer)
        await self.session.flush()
        return user
