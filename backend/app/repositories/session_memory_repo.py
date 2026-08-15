"""SessionMemory Repository — session_memories 表数据访问层"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.session_memory import SessionMemoryORM
from app.memory.schemas import SessionMemory, JobPreference
import uuid
from typing import Optional
from datetime import datetime


class SessionMemoryRepository:
    """session_memories 表 CRUD"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_thread(self, thread_id: str) -> Optional[SessionMemory]:
        """按 thread_id 获取对话状态（Pydantic）"""
        result = await self.db.execute(
            select(SessionMemoryORM).where(
                SessionMemoryORM.thread_id == thread_id
            )
        )
        orm = result.scalar_one_or_none()
        return orm.to_pydantic() if orm else None

    async def get_active_for_user(self, user_id: uuid.UUID) -> Optional[SessionMemory]:
        """获取用户最近更新的对话状态"""
        result = await self.db.execute(
            select(SessionMemoryORM)
            .where(SessionMemoryORM.user_id == user_id)
            .order_by(desc(SessionMemoryORM.last_updated_at))
            .limit(1)
        )
        orm = result.scalar_one_or_none()
        return orm.to_pydantic() if orm else None

    async def upsert(self, thread_id: str, user_id: uuid.UUID, payload: SessionMemory) -> None:
        """写入/更新对话状态"""
        result = await self.db.execute(
            select(SessionMemoryORM).where(
                SessionMemoryORM.thread_id == thread_id
            )
        )
        orm = result.scalar_one_or_none()

        if not orm:
            orm = SessionMemoryORM(thread_id=thread_id, user_id=user_id)
            self.db.add(orm)

        orm.preferences = payload.preferences.model_dump()
        orm.preference_sources = payload.preference_sources
        orm.open_questions = payload.open_questions
        orm.recent_decisions = payload.recent_decisions
        orm.current_goal = payload.current_goal
        orm.next_action = payload.next_action
        orm.last_updated_at = datetime.utcnow()

        await self.db.flush()

    async def list_for_user(
        self, user_id: uuid.UUID, limit: int = 10
    ) -> list[SessionMemory]:
        """获取用户最近的对话状态列表"""
        result = await self.db.execute(
            select(SessionMemoryORM)
            .where(SessionMemoryORM.user_id == user_id)
            .order_by(desc(SessionMemoryORM.last_updated_at))
            .limit(limit)
        )
        orms = result.scalars().all()
        return [orm.to_pydantic() for orm in orms]
