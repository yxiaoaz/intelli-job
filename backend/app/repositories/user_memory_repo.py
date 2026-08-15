"""UserMemory Repository — user_memories 表数据访问层"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user_memory import UserMemoryORM
from app.memory.schemas import UserMemory, JobPreference
import uuid
from typing import Optional
from datetime import datetime


class UserMemoryRepository:
    """user_memories 表 CRUD"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: uuid.UUID) -> Optional[UserMemory]:
        """获取用户长期记忆（Pydantic）"""
        result = await self.db.execute(
            select(UserMemoryORM).where(UserMemoryORM.user_id == user_id)
        )
        orm = result.scalar_one_or_none()
        return orm.to_pydantic() if orm else None

    async def upsert(self, user_id: uuid.UUID, payload: UserMemory) -> None:
        """写入/更新用户长期记忆"""
        result = await self.db.execute(
            select(UserMemoryORM).where(UserMemoryORM.user_id == user_id)
        )
        orm = result.scalar_one_or_none()

        if not orm:
            orm = UserMemoryORM(user_id=user_id)
            self.db.add(orm)

        orm.stable_facts = payload.stable_facts
        orm.long_term_preferences = payload.long_term_preferences.model_dump()
        orm.negative_signals = payload.negative_signals
        orm.career_direction = payload.career_direction
        orm.last_updated_at = datetime.utcnow()

        await self.db.flush()

    async def get_preferences(self, user_id: uuid.UUID) -> Optional[JobPreference]:
        """获取展平后的 JobPreference"""
        result = await self.db.execute(
            select(UserMemoryORM.long_term_preferences).where(
                UserMemoryORM.user_id == user_id
            )
        )
        row = result.one_or_none()
        if not row or not row[0]:
            return None
        return JobPreference(**row[0])

    async def merge_preferences(self, user_id: uuid.UUID, new: JobPreference) -> None:
        """增量合并 JobPreference（list 字段 append，其他 set）"""
        existing = await self.get_preferences(user_id)
        if existing:
            merged_data = existing.model_dump()
            new_data = new.model_dump()

            for key, new_val in new_data.items():
                old_val = merged_data.get(key, [])
                if isinstance(old_val, list) and isinstance(new_val, list):
                    # list 字段：append 去重
                    combined = list(old_val)
                    for item in new_val:
                        if item not in combined:
                            combined.append(item)
                    merged_data[key] = combined
                elif new_val is not None and new_val != {} and new_val != []:
                    # 非 list 字段：非空则覆盖
                    merged_data[key] = new_val

            merged = JobPreference(**merged_data)
        else:
            merged = new

        # 写回 DB
        result = await self.db.execute(
            select(UserMemoryORM).where(UserMemoryORM.user_id == user_id)
        )
        orm = result.scalar_one_or_none()
        if not orm:
            orm = UserMemoryORM(user_id=user_id)
            self.db.add(orm)

        orm.long_term_preferences = merged.model_dump()
        orm.last_updated_at = datetime.utcnow()
        await self.db.flush()
