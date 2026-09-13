from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
import uuid

from app.config import get_settings
from app.models.constants import ApplicationStatus
from app.memory.schemas import SalaryRange

_settings = get_settings()


# Auth Schemas
class UserRegister(BaseModel):
    username: str = Field(..., min_length=1, max_length=128, description="用户名")
    password: str = Field(..., min_length=8, description="密码至少8位")
    security_question: Optional[str] = Field(None, description="安全问题")
    security_answer: Optional[str] = Field(None, description="安全问题答案")


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    username: str
    is_active: bool
    created_at: datetime


# Resume Schemas
class ResumeUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    resume_name: str
    active_status: bool
    parsed_at: Optional[datetime] = None
    created_at: datetime


class ResumeParseRequest(BaseModel):
    resume_id: uuid.UUID


class ResumeUpdate(BaseModel):
    resume_name: Optional[str] = None
    extracted_content: Optional[dict] = None


class ResumeSummary(BaseModel):
    """列表页画像摘要（从最新 completed analysis 的 parsed_data/evaluation 提取）"""
    latest_title: Optional[str] = None       # 最近职位（position）
    latest_company: Optional[str] = None
    highest_degree: Optional[str] = None
    skills_preview: list[str] = []           # 前 5 个
    completeness: Optional[int] = None       # 评分的 completeness 维度（0-100）
    suggestion_count: int = 0                # 优化建议条数


class ResumeProfileUpdateRequest(BaseModel):
    """详情页画像校准请求（全部 optional，未传的 section 不动，传入的 section 整体替换）"""
    personal_info: Optional[dict] = None
    skills: Optional[list[str]] = None
    education: Optional[list[dict]] = None
    work_experience: Optional[list[dict]] = None


# Job Schemas
class JobMatchRequest(BaseModel):
    user_query_preference: Optional[dict] = {}
    user_resume_profile: Optional[dict] = {}
    search_mode: str = Field(
        default="hybrid",
        description="搜索模式：'hybrid'（混合）、'semantic'/'vector'（向量）、'sparse'/'keyword'（关键词）"
    )
    top_k: int = Field(default=100, ge=1, le=200)
    hard_filters: Optional[dict] = {}


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    company: str
    title: str
    recruitment_type: str
    location: str
    salary: str
    education: str
    update_time: Optional[str] = None
    description: str
    full_description: str
    url: str
    score: float
    is_bookmarked: bool = False


# Bookmark Schemas
class BookmarkCreate(BaseModel):
    job_id: uuid.UUID


class BookmarkUpdateRequest(BaseModel):
    """PATCH /bookmarks/{job_id} 请求体

    status/notes 均 optional，传哪个改哪个；None = 不修改该字段，
    notes 传空串表示清空备注（前端约定）。
    """
    status: Optional[ApplicationStatus] = None
    notes: Optional[str] = Field(None, max_length=2000)


class BookmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    job: JobResponse


# Chat Schemas
class ChatMessageRequest(BaseModel):
    # 单条消息长度上限（settings 驱动，import 时取值，改 env 重启生效）
    message: str = Field(
        ...,
        min_length=1,
        max_length=_settings.CHAT_MESSAGE_MAX_LENGTH,
    )


class ChatMessageResponse(BaseModel):
    reply: str
    session_id: uuid.UUID


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ChatMessageItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    message_metadata: dict | None = None


# Session Intent Schemas（求职意向：L1 会话记忆 + L2 长期偏好的合并视图）
class IntentSummary(BaseModel):
    """下发给前端的意向形状，字段名与 IntentDisplay / ContextPill 保持一致。

    注：老 `session_intents` 表里的 `experience` 已随记忆系统重构退役，不再
    返回（组件对它是条件渲染）；`filters` 保留为空 dict 以兼容旧调用方。
    """

    target_roles: list[str] = []
    locations: list[str] = []
    salary: Optional[SalaryRange] = None
    recruitment_types: list[str] = []
    industries: list[str] = []
    filters: dict = {}


class SessionIntentResponse(BaseModel):
    thread_id: str
    intent: Optional[IntentSummary] = None


class SessionIntentUpdateRequest(BaseModel):
    """用户在界面上显式确认的意向：None 表示该字段不改动，[] 表示清空"""

    target_roles: Optional[list[str]] = None
    locations: Optional[list[str]] = None
    recruitment_types: Optional[list[str]] = None
    industries: Optional[list[str]] = None
    salary: Optional[SalaryRange] = None


# Preference Schemas
class UserPreferenceUpdate(BaseModel):
    intended_company: Optional[list] = None
    intended_company_type: Optional[list] = None
    intended_location: Optional[list] = None
    intended_industry: Optional[list] = None
    intended_position: Optional[list] = None
    job_type: Optional[list] = None


class UserPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    user_id: uuid.UUID
    intended_company: list = []
    intended_company_type: list = []
    intended_location: list = []
    intended_industry: list = []
    intended_position: list = []
    job_type: list = []
    updated_at: datetime


# Password Change Schemas
class PasswordChangeRequest(BaseModel):
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=8, description="新密码，至少8位")


class PasswordChangeResponse(BaseModel):
    message: str = "密码修改成功"


# Security Question / Forgot Password Schemas
class ForgotPasswordRequest(BaseModel):
    username: str


class SecurityQuestionResponse(BaseModel):
    username: str
    security_question: str


class ResetPasswordRequest(BaseModel):
    username: str
    security_answer: str = Field(..., description="安全问题答案")
    new_password: str = Field(..., min_length=8, description="新密码，至少8位")


class ResetPasswordResponse(BaseModel):
    message: str = "密码重置成功"


class SetSecurityQuestionRequest(BaseModel):
    security_question: str = Field(..., description="安全问题")
    security_answer: str = Field(..., min_length=1, description="安全问题答案")


class SetSecurityQuestionResponse(BaseModel):
    message: str = "安全问题设置成功"


class SecurityQuestionStatusResponse(BaseModel):
    has_security_question: bool
