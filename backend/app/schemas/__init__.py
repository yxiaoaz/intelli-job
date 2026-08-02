from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
import uuid


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


class BookmarkUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class BookmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    notes: Optional[str] = None
    created_at: datetime
    job: JobResponse


# Chat Schemas
class ChatMessageRequest(BaseModel):
    message: str


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
