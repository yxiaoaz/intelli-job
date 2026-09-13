"""Memory Schemas — agent 记忆系统的真理 schema。

所有 ORM 列、markdown 章节、agent prompt 字段名都从这里派生。
"""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SalaryRange(BaseModel):
    """薪资期望（CNY 默认）"""

    min: int = Field(description="薪资下限（元/月）")
    max: Optional[int] = Field(default=None, description="薪资上限（元/月）")
    currency: str = Field(default="CNY", description="币种")


class JobPreference(BaseModel):
    """用户求职偏好的完整刻画"""

    target_roles: list[str] = Field(
        default_factory=list,
        description="期望岗位，如 '产品经理' 'AI产品经理'",
    )
    locations: list[str] = Field(
        default_factory=list,
        description="期望城市，如 '深圳' '广州'",
    )
    salary: Optional[SalaryRange] = Field(
        default=None,
        description="薪资期望",
    )
    recruitment_types: list[Literal["INTERN", "GRADUATE", "EXPERIENCED"]] = Field(
        default_factory=list,
        description="招聘类型",
    )
    industries: list[str] = Field(
        default_factory=list,
        description="期望行业",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="技能关键词",
    )
    target_companies: list[str] = Field(
        default_factory=list,
        description="期望公司，如 '字节' '腾讯'（来自 UserQueryPreference 合并）",
    )
    target_company_types: list[str] = Field(
        default_factory=list,
        description="期望公司类型，如 '大厂' '外企'（来自 UserQueryPreference 合并）",
    )


class UserMemory(BaseModel):
    """L2 — 用户长期记忆

    注：原 `stable_facts`（简历的有损投影）已随 agent-context-overhaul Phase 3 退役；
    简历原文由 DbBackend 渲染的 `/resume/active.md` 提供，信息更全且不会残留脏数据。
    """

    long_term_preferences: JobPreference = Field(
        default_factory=JobPreference,
        description="长期偏好（包含 UserQueryPreference 老表语义）",
    )
    preference_sources: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "偏好字段 → 写入来源，与 SessionMemory.preference_sources 同构。"
            "来源枚举：'user' / 'agent' / 'resume'，优先级 user > agent > resume，"
            "低优先级写入不得覆盖已有高优先级字段（写入仲裁）"
        ),
    )
    negative_signals: list[str] = Field(
        default_factory=list,
        description="用户不要的方向，如 '不做销售'",
    )
    career_direction: Optional[str] = Field(
        default=None,
        description="求职方向（一句话描述）",
    )
    last_updated: Optional[datetime] = Field(
        default=None,
        description="最后更新时间",
    )


class SessionMemory(BaseModel):
    """L1 — 单次对话状态"""

    current_goal: str = Field(
        default="auto",
        description="当前对话目标",
    )
    preferences: JobPreference = Field(
        default_factory=JobPreference,
        description=(
            "当前对话累积的偏好（合并 confirmed + inferred，"
            "用 preference_sources 字段追溯来源）"
        ),
    )
    preference_sources: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "字段 → 来源 映射。例如 "
            "{'locations': 'user_stated', 'salary': 'agent_inferred'}。"
            "来源枚举：'user_confirmed' / 'user_stated' / 'agent_inferred' / 'system_default'。"
        ),
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="待回答的问题",
    )
    recent_decisions: list[str] = Field(
        default_factory=list,
        description="近期决策（每轮 append）",
    )
    next_action: Optional[str] = Field(
        default=None,
        description="建议的 next action",
    )
    last_updated: Optional[datetime] = Field(
        default=None,
        description="最后更新时间",
    )
