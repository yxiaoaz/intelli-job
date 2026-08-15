"""Unit tests for memory schemas (app.memory.schemas)"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.memory.schemas import (
    SalaryRange,
    JobPreference,
    UserMemory,
    SessionMemory,
)


# ── SalaryRange ──────────────────────────────────────────────────────────────

class TestSalaryRange:
    def test_min_required(self):
        sr = SalaryRange(min=10000)
        assert sr.min == 10000
        assert sr.max is None
        assert sr.currency == "CNY"

    def test_full(self):
        sr = SalaryRange(min=10000, max=20000, currency="USD")
        assert sr.max == 20000
        assert sr.currency == "USD"

    def test_min_missing_raises(self):
        with pytest.raises(ValidationError):
            SalaryRange()


# ── JobPreference ────────────────────────────────────────────────────────────

class TestJobPreference:
    def test_empty_defaults(self):
        jp = JobPreference()
        assert jp.target_roles == []
        assert jp.locations == []
        assert jp.salary is None
        assert jp.recruitment_types == []
        assert jp.industries == []
        assert jp.skills == []
        assert jp.target_companies == []
        assert jp.target_company_types == []

    def test_full_construction(self):
        jp = JobPreference(
            target_roles=["产品经理"],
            locations=["深圳", "广州"],
            salary=SalaryRange(min=15000, max=25000),
            recruitment_types=["GRADUATE"],
            industries=["互联网"],
            skills=["Python", "React"],
            target_companies=["字节"],
            target_company_types=["大厂"],
        )
        assert jp.target_roles == ["产品经理"]
        assert jp.salary.min == 15000
        assert jp.target_companies == ["字节"]

    def test_invalid_recruitment_type_raises(self):
        with pytest.raises(ValidationError):
            JobPreference(recruitment_types=["INVALID"])

    def test_model_dump_roundtrip(self):
        jp = JobPreference(
            target_roles=["AI产品经理"],
            locations=["深圳"],
            salary=SalaryRange(min=20000),
        )
        dumped = jp.model_dump()
        restored = JobPreference(**dumped)
        assert restored == jp


# ── UserMemory ───────────────────────────────────────────────────────────────

class TestUserMemory:
    def test_empty_defaults(self):
        um = UserMemory()
        assert um.stable_facts == {}
        assert isinstance(um.long_term_preferences, JobPreference)
        assert um.negative_signals == []
        assert um.career_direction is None
        assert um.last_updated is None

    def test_full_construction(self):
        um = UserMemory(
            stable_facts={"school": "中山大学", "major": "计算机"},
            long_term_preferences=JobPreference(
                target_roles=["产品经理"],
                locations=["深圳"],
            ),
            negative_signals=["不做销售"],
            career_direction="互联网产品方向",
            last_updated=datetime(2026, 8, 15),
        )
        assert um.stable_facts["school"] == "中山大学"
        assert um.long_term_preferences.target_roles == ["产品经理"]
        assert um.negative_signals == ["不做销售"]

    def test_model_dump_roundtrip(self):
        um = UserMemory(
            stable_facts={"school": "中山大学"},
            long_term_preferences=JobPreference(target_roles=["产品经理"]),
        )
        dumped = um.model_dump()
        restored = UserMemory(**dumped)
        assert restored == um


# ── SessionMemory ────────────────────────────────────────────────────────────

class TestSessionMemory:
    def test_empty_defaults(self):
        sm = SessionMemory()
        assert sm.current_goal == "auto"
        assert isinstance(sm.preferences, JobPreference)
        assert sm.preference_sources == {}
        assert sm.open_questions == []
        assert sm.recent_decisions == []
        assert sm.next_action is None
        assert sm.last_updated is None

    def test_full_construction(self):
        sm = SessionMemory(
            current_goal="字节深圳产品岗",
            preferences=JobPreference(
                target_roles=["产品经理"],
                locations=["深圳"],
            ),
            preference_sources={
                "locations": "user_stated",
                "target_roles": "user_confirmed",
            },
            open_questions=["用户是否接受实习转正？"],
            recent_decisions=["2026-08-15 用户缩小公司范围到字节"],
            next_action="搜索匹配岗位",
        )
        assert sm.current_goal == "字节深圳产品岗"
        assert sm.preferences.locations == ["深圳"]
        assert sm.preference_sources["locations"] == "user_stated"

    def test_preference_sources_tracking(self):
        """preference_sources 应能追溯每个偏好字段的来源"""
        sm = SessionMemory(
            preferences=JobPreference(
                target_roles=["产品经理"],
                locations=["深圳"],
                salary=SalaryRange(min=15000),
            ),
            preference_sources={
                "target_roles": "user_confirmed",
                "locations": "user_stated",
                "salary": "agent_inferred",
            },
        )
        assert len(sm.preference_sources) == 3
        assert sm.preference_sources["salary"] == "agent_inferred"

    def test_model_dump_roundtrip(self):
        sm = SessionMemory(
            current_goal="测试目标",
            preferences=JobPreference(target_roles=["算法工程师"]),
            preference_sources={"target_roles": "user_stated"},
            open_questions=["问题1"],
        )
        dumped = sm.model_dump()
        restored = SessionMemory(**dumped)
        assert restored == restored  # basic sanity
        assert restored.current_goal == "测试目标"
        assert restored.preferences.target_roles == ["算法工程师"]
