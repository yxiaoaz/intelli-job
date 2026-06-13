"""Session Intent Model - 存储用户会话级别的结构化求职意向"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.models.base import Base


class SessionIntent(Base):
    """Session 级别的意图记忆表
    
    用于存储用户在当前对话会话中的结构化求职意向，
    支持多轮对话中的意图追踪和精准搜索。
    """
    
    __tablename__ = "session_intents"
    
    # 主键
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 外键关联
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id"), 
        nullable=False, 
        index=True
    )
    thread_id = Column(
        String(255), 
        unique=True, 
        nullable=False, 
        index=True
    )  # LangGraph thread_id
    
    # 用户求职偏好（完整字段）
    preferred_city = Column(
        JSONB, 
        default=list, 
        server_default="[]"
    )  # ["深圳", "广州"]
    
    preferred_job_titles = Column(
        JSONB, 
        default=list, 
        server_default="[]"
    )  # ["算法工程师", "AI产品经理"]
    
    salary_expectation = Column(
        JSONB, 
        nullable=True
    )  # {"min": 15000, "max": 25000, "currency": "CNY"}
    
    skills = Column(
        JSONB, 
        default=list, 
        server_default="[]"
    )  # ["Python", "PyTorch", "NLP"]
    
    education_level = Column(
        String(50), 
        nullable=True
    )  # "硕士"
    
    work_experience_years = Column(
        Integer, 
        nullable=True
    )  # 2
    
    search_direction = Column(
        String(100), 
        nullable=True
    )  # "AI算法方向" - 用于方向切换
    
    # 简历关联
    resume_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("resumes.id"), 
        nullable=True
    )
    
    include_resume_in_search = Column(
        Boolean, 
        default=True, 
        nullable=False
    )
    
    # 时间戳
    last_updated_at = Column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    created_at = Column(
        DateTime, 
        default=datetime.utcnow
    )
    
    # 关系
    user = relationship("User", back_populates="session_intents")
    resume = relationship("Resume", back_populates="session_intents")
    
    def __repr__(self):
        return f"<SessionIntent(thread_id='{self.thread_id}', direction='{self.search_direction}')>"
