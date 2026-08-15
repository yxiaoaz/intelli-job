"""Unit tests for UserMemoryORM and SessionMemoryORM model definitions."""
import pytest
import uuid
from datetime import datetime

from app.models.user_memory import UserMemoryORM
from app.models.session_memory import SessionMemoryORM
from app.memory.schemas import UserMemory, SessionMemory, JobPreference


# ── UserMemoryORM ──────────────────────────────────────────────────────────

class TestUserMemoryORM:
    def test_table_name(self):
        assert UserMemoryORM.__tablename__ == "user_memories"

    def test_has_required_columns(self):
        """验证 ORM 定义了所有预期列"""
        col_names = {c.name for c in UserMemoryORM.__table__.columns}
        expected = {
            "user_id", "stable_facts", "long_term_preferences",
            "negative_signals", "career_direction",
            "last_updated_at", "created_at",
        }
        assert expected.issubset(col_names)

    def test_to_pydantic_empty(self):
        """空 ORM 对象 → 默认 Pydantic"""
        orm = UserMemoryORM(
            user_id=uuid.uuid4(),
            stable_facts={},
            long_term_preferences={},
            negative_signals=[],
            career_direction=None,
            last_updated_at=datetime.utcnow(),
        )
        pm = orm.to_pydantic()
        assert isinstance(pm, UserMemory)
        assert pm.stable_facts == {}
        assert isinstance(pm.long_term_preferences, JobPreference)
        assert pm.long_term_preferences.target_roles == []
        assert pm.negative_signals == []

    def test_to_pydantic_with_data(self):
        """带数据的 ORM → Pydantic 转换"""
        uid = uuid.uuid4()
        prefs = {
            "target_roles": ["产品经理"],
            "locations": ["深圳"],
            "salary": {"min": 15000, "max": 25000, "currency": "CNY"},
            "target_companies": ["字节"],
            "target_company_types": ["大厂"],
            "industries": ["AI"],
            "recruitment_types": ["EXPERIENCED"],
            "skills": ["Python"],
        }
        orm = UserMemoryORM(
            user_id=uid,
            stable_facts={"name": "测试"},
            long_term_preferences=prefs,
            negative_signals=["不喜欢夜班"],
            career_direction="AI方向",
            last_updated_at=datetime(2025, 1, 1),
        )
        pm = orm.to_pydantic()
        assert pm.stable_facts == {"name": "测试"}
        assert pm.long_term_preferences.target_roles == ["产品经理"]
        assert pm.long_term_preferences.locations == ["深圳"]
        assert pm.long_term_preferences.salary.min == 15000
        assert pm.long_term_preferences.target_companies == ["字节"]
        assert pm.long_term_preferences.recruitment_types == ["EXPERIENCED"]
        assert pm.negative_signals == ["不喜欢夜班"]
        assert pm.career_direction == "AI方向"


# ── SessionMemoryORM ──────────────────────────────────────────────────────

class TestSessionMemoryORM:
    def test_table_name(self):
        assert SessionMemoryORM.__tablename__ == "session_memories"

    def test_has_required_columns(self):
        col_names = {c.name for c in SessionMemoryORM.__table__.columns}
        expected = {
            "id", "user_id", "thread_id",
            "preferences", "preference_sources",
            "open_questions", "recent_decisions",
            "current_goal", "next_action",
            "last_updated_at", "created_at",
        }
        assert expected.issubset(col_names)

    def test_to_pydantic_empty(self):
        orm = SessionMemoryORM(
            user_id=uuid.uuid4(),
            thread_id="thread-1",
            preferences={},
            preference_sources={},
            open_questions=[],
            recent_decisions=[],
            current_goal="auto",
            next_action=None,
            last_updated_at=datetime.utcnow(),
        )
        pm = orm.to_pydantic()
        assert isinstance(pm, SessionMemory)
        assert pm.current_goal == "auto"
        assert isinstance(pm.preferences, JobPreference)
        assert pm.open_questions == []

    def test_to_pydantic_with_data(self):
        prefs = {
            "target_roles": ["AI产品经理"],
            "locations": ["北京"],
        }
        orm = SessionMemoryORM(
            user_id=uuid.uuid4(),
            thread_id="thread-2",
            preferences=prefs,
            preference_sources={"target_roles": "user_explicit"},
            open_questions=["是否接受实习？"],
            recent_decisions=["选择北京"],
            current_goal="找AI产品岗",
            next_action="搜索岗位",
            last_updated_at=datetime(2025, 6, 1),
        )
        pm = orm.to_pydantic()
        assert pm.current_goal == "找AI产品岗"
        assert pm.preferences.target_roles == ["AI产品经理"]
        assert pm.preferences.locations == ["北京"]
        assert pm.preference_sources == {"target_roles": "user_explicit"}
        assert pm.open_questions == ["是否接受实习？"]
        assert pm.next_action == "搜索岗位"
