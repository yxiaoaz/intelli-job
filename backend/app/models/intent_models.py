"""Intent 数据模型定义

用于结构化表示用户的求职意向。
Agent 在写入 Markdown 文件时应遵循此结构。
"""

from typing import Optional
from pydantic import BaseModel, Field


class SalaryExpectation(BaseModel):
    """薪资期望"""
    min: int = Field(description="最低薪资（元/月）", ge=0)
    max: int = Field(description="最高薪资（元/月）", ge=0)
    currency: str = Field(default="CNY", description="货币单位")


class IntentStructure(BaseModel):
    """Intent 数据结构定义
    
    Agent 在写入 Markdown 文件时，应遵循此结构。
    字段说明：
    - preferred_city: 意向城市列表，如 ["深圳", "北京"]
    - preferred_job_titles: 意向岗位列表，如 ["产品经理", "AI 产品经理"]
    - salary_expectation: 薪资期望范围
    - skills: 技能列表，如 ["Python", "React", "NLP"]
    - search_direction: 求职方向标签，如 "AI 产品方向"
    - should_search_now: 是否应该立即执行搜索
    - search_keywords: 搜索关键词
    - reasoning: 推理过程，解释为什么做出这些判断
    """
    preferred_city: Optional[list[str]] = Field(
        default=None,
        description="意向城市列表"
    )
    preferred_job_titles: Optional[list[str]] = Field(
        default=None,
        description="意向岗位名称列表"
    )
    salary_expectation: Optional[SalaryExpectation] = Field(
        default=None,
        description="薪资期望范围"
    )
    skills: Optional[list[str]] = Field(
        default=None,
        description="技能列表"
    )
    search_direction: Optional[str] = Field(
        default=None,
        description="求职方向标签"
    )
    should_search_now: bool = Field(
        default=False,
        description="是否应该立即执行搜索"
    )
    search_keywords: Optional[str] = Field(
        default=None,
        description="搜索关键词"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="推理过程"
    )
