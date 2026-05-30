import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON, Uuid, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.models.constants import JobSource, RecruitmentType, AcademicQualification, ApplicationStatus


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    query_preferences = relationship("UserQueryPreference", back_populates="user", cascade="all, delete-orphan")
    bookmarks = relationship("JobBookmark", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(email='{self.email}')>"


class Resume(Base):
    """简历模型"""
    __tablename__ = "resumes"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    active_status = Column(Boolean, default=True, comment="是否活跃简历")
    resume_name = Column(String(128), default="我的简历")
    oss_key = Column(String(512), comment="OSS文件路径")
    extracted_content = Column(JSON, comment="解析后的简历内容")
    parsed_at = Column(DateTime, comment="最后解析时间")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="resumes")

    def __repr__(self):
        return f"<Resume(name='{self.resume_name}', user_id={self.user_id})>"


class UserQueryPreference(Base):
    """用户求职偏好模型"""
    __tablename__ = "user_query_preferences"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    intended_company = Column(JSON, default=list, comment="意向公司")
    intended_company_type = Column(JSON, default=list, comment="意向公司类型")
    intended_location = Column(JSON, default=list, comment="意向地点")
    intended_industry = Column(JSON, default=list, comment="意向行业")
    intended_position = Column(JSON, default=list, comment="意向职位")
    job_type = Column(JSON, default=list, comment="工作类型")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="query_preferences")

    def __repr__(self):
        return f"<UserQueryPreference(user_id={self.user_id})>"


class JobItem(Base):
    """职位模型"""
    __tablename__ = "job_items"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    
    # Tracing info
    source = Column(SQLEnum(JobSource), comment="职位来源平台")
    url = Column(String(512), unique=True, comment="职位URL")
    fingerprint = Column(String(64), unique=True, index=True, comment="去重指纹")
    
    # Embedding info
    embedding_generated = Column(Boolean, default=False, comment="是否已生成向量")
    
    # Basic info
    job_title = Column(String(256), comment="职位标题")
    update_time = Column(DateTime, nullable=True, comment="更新时间")
    location = Column(String(128), comment="工作地点")
    recruitment_type = Column(SQLEnum(RecruitmentType), comment="招聘类型")
    min_academic_qualification = Column(
        SQLEnum(AcademicQualification), 
        default=AcademicQualification.ALL,
        comment="最低学历要求"
    )
    salary = Column(String(128), default="NA", comment="薪资")
    description = Column(Text, comment="职位描述")
    
    # Company info
    company_name = Column(String(256), comment="公司名称")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bookmarks = relationship("JobBookmark", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<JobItem(title='{self.job_title}', company='{self.company_name}')>"


class JobBookmark(Base):
    """职位收藏模型"""
    __tablename__ = "job_bookmarks"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Uuid, ForeignKey("job_items.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(
        SQLEnum(ApplicationStatus), 
        default=ApplicationStatus.SAVED,
        comment="申请状态"
    )
    notes = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="bookmarks")
    job = relationship("JobItem", back_populates="bookmarks")

    def __repr__(self):
        return f"<JobBookmark(user_id={self.user_id}, job_id={self.job_id})>"


class ChatSession(Base):
    """对话会话模型"""
    __tablename__ = "chat_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(256), comment="会话标题")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatSession(user_id={self.user_id}, title='{self.title}')>"


class ChatMessage(Base):
    """对话消息模型"""
    __tablename__ = "chat_messages"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id = Column(Uuid, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    
    role = Column(String(16), nullable=False, comment="角色: user/assistant/system")
    content = Column(Text, nullable=False, comment="消息内容")
    message_metadata = Column(JSON, comment="元数据(工具调用记录等)")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(session_id={self.session_id}, role='{self.role}')>"
