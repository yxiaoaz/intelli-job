"""SessionMemory ORM — L1 对话状态表（rename from session_intents）"""

from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.models.base import Base


class SessionMemoryORM(Base):
    """L1 — 对话状态 ORM（rename from session_intents，合并 confirmed/inferred → preferences）"""

    __tablename__ = "session_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 外键
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    thread_id = Column(String(255), index=True)  # LangGraph thread_id

    # 嵌套 JSONB 列（合并 confirmed + inferred → preferences）
    preferences = Column(JSONB, default=dict, server_default="{}", nullable=False)
    preference_sources = Column(JSONB, default=dict, server_default="{}", nullable=False)
    open_questions = Column(JSONB, default=list, server_default="[]", nullable=False)
    recent_decisions = Column(JSONB, default=list, server_default="[]", nullable=False)

    # 标量列
    current_goal = Column(String(500), default="auto")
    next_action = Column(String(500), nullable=True)

    # 时间戳
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    user = relationship("User")

    def to_pydantic(self) -> "SessionMemory":
        from app.memory.schemas import SessionMemory, JobPreference
        return SessionMemory(
            current_goal=self.current_goal or "auto",
            preferences=JobPreference(**(self.preferences or {})),
            preference_sources=self.preference_sources or {},
            open_questions=self.open_questions or [],
            recent_decisions=self.recent_decisions or [],
            next_action=self.next_action,
            last_updated=self.last_updated_at,
        )
