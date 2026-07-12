"""Agent Memory & Profile Pydantic Models

定义 Agent 记忆架构中的核心数据结构，用于序列化和反序列化文件内容。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SalaryRange(BaseModel):
    """薪资范围"""
    min: int = Field(description="最低薪资（元/月）", ge=0)
    max: Optional[int] = Field(None, description="最高薪资（元/月）", ge=0)
    currency: str = Field(default="CNY", description="货币单位")


class ExperienceFilter(BaseModel):
    """经验过滤条件"""
    preferred_min_years: Optional[int] = Field(None, description="期望最低年限")
    preferred_max_years: Optional[int] = Field(None, description="期望最高年限")
    avoid_above_years: Optional[int] = Field(None, description="避免超过该年限的岗位")


class SearchIntent(BaseModel):
    """搜索意图契约 (search_intent.json)"""
    version: str = Field(default="1.0")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    target_roles: List[str] = Field(default_factory=list, description="目标岗位列表")
    locations: List[str] = Field(default_factory=list, description="意向城市列表")
    salary: Optional[SalaryRange] = Field(None, description="薪资期望")
    experience: Optional[ExperienceFilter] = Field(None, description="经验要求过滤")
    
    recruitment_types: List[str] = Field(default_factory=list, description="招聘类型：EXPERIENCED, CAMPUS")
    industries: List[str] = Field(default_factory=list, description="偏好行业")
    
    filters: Dict[str, Any] = Field(default_factory=dict, description="其他过滤条件，如 exclude_keywords")


class SessionState(BaseModel):
    """会话工作状态 (session.md 核心状态)"""
    current_goal: str = Field(description="当前求职目标简述")
    confirmed_preferences: List[str] = Field(default_factory=list, description="用户明确确认的偏好")
    inferred_preferences: List[str] = Field(default_factory=list, description="Agent 推断的偏好")
    open_questions: List[str] = Field(default_factory=list, description="待向用户澄清的问题")
    recent_decisions: List[str] = Field(default_factory=list, description="最近的决策摘要")
    next_action: Optional[str] = Field(None, description="下一步建议动作")


class UserProfile(BaseModel):
    """用户长期画像 (profile.md)"""
    stable_facts: Dict[str, Any] = Field(default_factory=dict, description="来自简历的稳定事实")
    long_term_preferences: Dict[str, Any] = Field(default_factory=dict, description="长期确认的偏好")
    negative_signals: List[str] = Field(default_factory=list, description="明确的负面偏好（不看什么）")
    career_direction: Optional[str] = Field(None, description="职业发展方向描述")
    last_updated: Optional[datetime] = Field(None, description="最后更新时间")


class EventLog(BaseModel):
    """事件日志条目 (events.jsonl)"""
    ts: datetime = Field(default_factory=datetime.utcnow)
    type: str = Field(description="事件类型：user_message, search_executed, user_feedback, intent_updated")
    content: Optional[str] = Field(None, description="事件内容或摘要")
    metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据")
