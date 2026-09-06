import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON, Uuid, Enum as SQLEnum, Integer, BigInteger, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.models.constants import JobSource, RecruitmentType, AcademicQualification, ApplicationStatus
from app.models.session_memory import SessionMemoryORM
from app.models.user_memory import UserMemoryORM


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    username = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    security_question = Column(String(256), nullable=True, comment="安全问题")
    security_answer_hash = Column(String(256), nullable=True, comment="安全问题答案的bcrypt哈希")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    bookmarks = relationship("JobBookmark", back_populates="user", cascade="all, delete-orphan")
    job_ai_explanations = relationship("JobAIExplanation", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    user_memory = relationship("UserMemoryORM", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(username='{self.username}')>"


class Resume(Base):
    """简历模型"""
    __tablename__ = "resumes"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 文件信息
    filename = Column(String(256), comment="原始文件名")
    file_path = Column(String(512), comment="文件存储路径")
    file_size = Column(Integer, comment="文件大小（字节）")
    content_type = Column(String(128), comment="文件MIME类型")
    
    active_status = Column(Boolean, default=False, comment="是否活跃简历（互斥，每用户至多一份）")
    resume_name = Column(String(128), default="我的简历")
    oss_key = Column(String(512), comment="OSS文件路径（保留兼容）")
    extracted_content = Column(JSON, comment="解析后的简历内容")
    parsed_at = Column(DateTime, comment="最后解析时间")
    uploaded_at = Column(DateTime, default=datetime.utcnow, comment="上传时间")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="resumes")
    analyses = relationship("ResumeAnalysis", back_populates="resume", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Resume(name='{self.resume_name}', user_id={self.user_id})>"


# UserQueryPreference 已合并到 UserMemoryORM.long_term_preferences（memory-system-redesign）


class JobItem(Base):
    """职位模型"""
    __tablename__ = "job_items"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    
    # Tracing info
    source = Column(SQLEnum(JobSource, values_callable=lambda x: [e.value for e in x]), comment="职位来源平台")
    url = Column(String(512), unique=True, comment="职位URL")
    fingerprint = Column(String(64), unique=True, index=True, comment="去重指纹")
    
    # Embedding info
    embedding_generated = Column(Boolean, default=False, comment="是否已生成向量")
    
    # Basic info
    job_title = Column(String(256), comment="职位标题")
    update_time = Column(DateTime, nullable=True, comment="更新时间")
    location = Column(String(128), comment="工作地点")
    recruitment_type = Column(SQLEnum(RecruitmentType, values_callable=lambda x: [e.value for e in x]), comment="招聘类型")
    min_academic_qualification = Column(
        SQLEnum(AcademicQualification, values_callable=lambda x: [e.value for e in x]), 
        default=AcademicQualification.ALL,
        comment="最低学历要求"
    )
    salary = Column(String(128), default="NA", comment="薪资")
    # 新增三列（job-source-adapter-refactor）：均 nullable
    published_at = Column(DateTime(timezone=True), nullable=True, comment="发布时间（TIMESTAMPTZ，源站提供）")
    salary_min = Column(BigInteger, nullable=True, comment="结构化薪资下限")
    salary_max = Column(BigInteger, nullable=True, comment="结构化薪资上限")
    description = Column(Text, comment="职位描述")
    
    # Company info
    company_name = Column(String(256), comment="公司名称")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bookmarks = relationship("JobBookmark", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<JobItem(title='{self.job_title}', company='{self.company_name}')>"

    @staticmethod
    def from_scrapy_item(scrapy_job_item):
        """从 Scrapy Item 创建 JobItem 实例"""
        import uuid as uuid_module
        return JobItem(
            id=scrapy_job_item.get("id") or uuid_module.uuid4(),
            source=scrapy_job_item.get("source"),
            url=scrapy_job_item.get("url"),
            fingerprint=scrapy_job_item.get("fingerprint"),
            job_title=scrapy_job_item.get("job_title"),
            update_time=scrapy_job_item.get("update_time"),
            location=scrapy_job_item.get("location"),
            recruitment_type=scrapy_job_item.get("recruitment_type"),
            min_academic_qualification=scrapy_job_item.get("min_academic_qualification", AcademicQualification.ALL),
            salary=scrapy_job_item.get("salary", "NA"),
            published_at=scrapy_job_item.get("published_at"),
            salary_min=scrapy_job_item.get("salary_min"),
            salary_max=scrapy_job_item.get("salary_max"),
            description=scrapy_job_item.get("description"),
            company_name=scrapy_job_item.get("company_name"),
        )

    def __str__(self):
        """用于生成 embedding 的文本表示"""
        import json
        return json.dumps(
            {
                "岗位名称 (Job Title)": self.job_title,
                "公司名称 (Company Name)": self.company_name,
                "最低学历要求 (Minimum Academic Qualification)": self.min_academic_qualification.value if self.min_academic_qualification else None,
                "薪资 (Salary)": self.salary,
                "工作地点 (Location)": self.location,
                "招聘类型 (Recruitment Type)": self.recruitment_type.value if self.recruitment_type else None,
                "工作描述 (Duties and Qualifications)": self.description,
            },
            ensure_ascii=False,
        )

    def to_dict(self):
        """转换为字典"""
        return {
            "id": str(self.id) if self.id else None,
            "source": self.source.value if self.source else None,
            "url": self.url,
            "embedding_generated": self.embedding_generated,
            "job_title": self.job_title,
            "update_time": self.update_time.isoformat() if self.update_time else None,
            "location": self.location,
            "recruitment_type": self.recruitment_type.value if self.recruitment_type else None,
            "min_academic_qualification": self.min_academic_qualification.value if self.min_academic_qualification else None,
            "salary": self.salary,
            "description": self.description,
            "company_name": self.company_name,
        }


class JobSourceHealth(Base):
    """源健康度（job-source-adapter-refactor 决策 5）

    计数语义：仅 FETCH_FAILED 计入 consecutive_fail；EMPTY 不计失败；
    NO_BOARD 独立计数（consecutive_no_board），连续≥3 联动注册表标 DEAD。
    """
    __tablename__ = "job_source_health"

    source = Column(
        SQLEnum(JobSource, values_callable=lambda x: [e.value for e in x]),
        primary_key=True, comment="职位来源平台",
    )
    last_ok_at = Column(DateTime, nullable=True, comment="最近成功时间")
    last_run_at = Column(DateTime, nullable=True, comment="最近运行时间")
    ok_count = Column(Integer, default=0, comment="成功条目累计")
    fail_count = Column(Integer, default=0, comment="失败批次累计（仅 FETCH_FAILED）")
    consecutive_fail = Column(Integer, default=0, comment="连续失败（仅 FETCH_FAILED）")
    consecutive_no_board = Column(Integer, default=0, comment="连续 NO_BOARD 批次（联动注册表 DEAD）")
    status = Column(String(16), default="ACTIVE", comment="ACTIVE / DEGRADED / DISABLED")
    note = Column(String(512), nullable=True, comment="最近错误摘要")

    def __repr__(self):
        return f"<JobSourceHealth(source={self.source}, status={self.status})>"


class JobAtsRegistry(Base):
    """公司 → ATS 映射注册表（ats-job-source-integration）

    ATS 路线的持续成本是"公司→ATS 映射"，本表把这份成本资产化。
    spider 只读 status=VERIFIED 的行；种子以 UNVERIFIED 灌入，由探测脚本升级。
    """
    __tablename__ = "company_ats_registry"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    company_name = Column(String(256), nullable=False, comment="展示名")
    ats_type = Column(String(32), nullable=False,
                      comment="greenhouse/lever/ashby/workable/smartrecruiters/recruitee")
    board_slug = Column(String(128), nullable=False, comment="board 标识")
    careers_url = Column(String(512), nullable=True, comment="官网 careers 页（探测溯源用）")
    status = Column(String(16), default="UNVERIFIED",
                    comment="VERIFIED / UNVERIFIED / DEAD")
    verified_at = Column(DateTime, nullable=True, comment="最近探测成功时间（复检依据）")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("ats_type", "board_slug", name="uq_ats_board"),
    )

    def __repr__(self):
        return (f"<JobAtsRegistry(company={self.company_name}, "
                f"ats={self.ats_type}, slug={self.board_slug}, status={self.status})>")


class JobBookmark(Base):
    """职位收藏模型"""
    __tablename__ = "job_bookmarks"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Uuid, ForeignKey("job_items.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(
        SQLEnum(ApplicationStatus, values_callable=lambda x: [e.value for e in x]), 
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


class JobAIExplanation(Base):
    """AI 岗位解释缓存（按用户隔离）"""
    __tablename__ = "job_ai_explanations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Uuid, ForeignKey("job_items.id", ondelete="CASCADE"), nullable=False)
    
    # 结构化解释数据
    match_score = Column(Integer, comment="AI 匹配度评分 0-100")
    match_reasons = Column(JSON, comment="匹配原因列表")
    match_risks = Column(JSON, comment="风险/差距列表")
    resume_tips = Column(JSON, comment="简历修改建议列表")
    
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'job_id', name='uq_user_job_explanation'),
    )

    # Relationships
    user = relationship("User", back_populates="job_ai_explanations")
    job = relationship("JobItem")

    def __repr__(self):
        return f"<JobAIExplanation(user_id={self.user_id}, job_id={self.job_id}, score={self.match_score})>"


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


class ResumeAnalysis(Base):
    """简历分析结果模型"""
    __tablename__ = "resume_analyses"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    resume_id = Column(Uuid, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    
    # 解析数据
    parsed_data = Column(JSON, comment="结构化解析数据（教育、工作、技能等）")
    
    # 评估报告
    evaluation = Column(JSON, comment="质量评估报告（评分、建议等）")
    
    # 状态管理
    status = Column(String(32), default="pending", comment="分析状态: pending/processing/completed/failed")
    error_message = Column(Text, comment="错误信息（如果失败）")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    resume = relationship("Resume", back_populates="analyses")

    def __repr__(self):
        return f"<ResumeAnalysis(resume_id={self.resume_id}, status='{self.status}')>"
