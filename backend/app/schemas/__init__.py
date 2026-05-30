from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
import uuid


# Auth Schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="密码至少8位")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Resume Schemas
class ResumeUploadResponse(BaseModel):
    id: uuid.UUID
    resume_name: str
    active_status: bool
    parsed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ResumeParseRequest(BaseModel):
    resume_id: uuid.UUID


class ResumeUpdate(BaseModel):
    resume_name: Optional[str] = None
    extracted_content: Optional[dict] = None


# Job Schemas
class JobMatchRequest(BaseModel):
    user_query_preference: Optional[dict] = {}
    user_resume_profile: Optional[dict] = {}
    search_mode: str = "hybrid"
    top_k: int = Field(default=100, ge=1, le=200)
    hard_filters: Optional[dict] = {}


class JobResponse(BaseModel):
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

    class Config:
        from_attributes = True


# Bookmark Schemas
class BookmarkCreate(BaseModel):
    job_id: uuid.UUID


class BookmarkUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class BookmarkResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    notes: Optional[str] = None
    created_at: datetime
    job: JobResponse

    class Config:
        from_attributes = True


# Chat Schemas
class ChatMessageRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    reply: str
    session_id: uuid.UUID


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Preference Schemas
class UserPreferenceUpdate(BaseModel):
    intended_company: Optional[list] = None
    intended_company_type: Optional[list] = None
    intended_location: Optional[list] = None
    intended_industry: Optional[list] = None
    intended_position: Optional[list] = None
    job_type: Optional[list] = None


class UserPreferenceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    intended_company: list = []
    intended_company_type: list = []
    intended_location: list = []
    intended_industry: list = []
    intended_position: list = []
    job_type: list = []
    updated_at: datetime

    class Config:
        from_attributes = True
