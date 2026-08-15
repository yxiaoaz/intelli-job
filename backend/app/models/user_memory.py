"""UserMemory ORM — L2 用户长期记忆表"""

from sqlalchemy import Column, String, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.models.base import Base


class UserMemoryORM(Base):
    """L2 — 用户长期记忆 ORM（包含 UserQueryPreference 合并字段）"""

    __tablename__ = "user_memories"

    # PK = user_id（一对一）
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # 嵌套 JSONB 列（与 Pydantic UserMemory + JobPreference 同构）
    stable_facts = Column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )
    long_term_preferences = Column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
        comment="嵌套 JobPreference 对象（含 target_roles / locations / salary / ...）",
    )
    negative_signals = Column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
    )

    # 标量列
    career_direction = Column(
        String(500),
        nullable=True,
    )

    # 时间戳
    last_updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    # 关系
    user = relationship("User", back_populates="user_memory")

    def to_pydantic(self) -> "UserMemory":
        from app.memory.schemas import UserMemory, JobPreference
        return UserMemory(
            stable_facts=self.stable_facts or {},
            long_term_preferences=JobPreference(**(self.long_term_preferences or {})),
            negative_signals=self.negative_signals or [],
            career_direction=self.career_direction,
            last_updated=self.last_updated_at,
        )
