"""MemoryService.merge_session_updates 单元测试。

覆盖：
- merge 模式 append 去重
- replace 模式覆盖 pref list 字段
- open_questions / recent_decisions 不受 mode 影响（始终 append）
- 标量字段直接覆盖
- 嵌套非 list 字段 set
"""
import pytest
from unittest.mock import MagicMock

from app.memory.service import MemoryService
from app.memory.schemas import SessionMemory, JobPreference, SalaryRange


@pytest.fixture
def memory_service():
    """构造 MemoryService（mock db，merge_session_updates 不依赖 db）。"""
    svc = MemoryService.__new__(MemoryService)
    svc.db = MagicMock()
    return svc


# ── merge 模式 ────────────────────────────────────────────────────────────

class TestMergeMode:
    @pytest.mark.asyncio
    async def test_append_dedup(self, memory_service):
        """merge 模式下 locations append 去重。"""
        current = SessionMemory(
            preferences=JobPreference(locations=["北京"])
        )
        updates = {"preferences": {"locations": ["上海"]}}
        result = await memory_service.merge_session_updates(current, updates, mode="merge")
        assert result.preferences.locations == ["北京", "上海"]

    @pytest.mark.asyncio
    async def test_no_duplicate(self, memory_service):
        """merge 模式下重复值不重复添加。"""
        current = SessionMemory(
            preferences=JobPreference(locations=["北京"])
        )
        updates = {"preferences": {"locations": ["北京"]}}
        result = await memory_service.merge_session_updates(current, updates, mode="merge")
        assert result.preferences.locations == ["北京"]

    @pytest.mark.asyncio
    async def test_multiple_fields(self, memory_service):
        """merge 模式同时更新多个 pref 字段。"""
        current = SessionMemory(
            preferences=JobPreference(
                target_roles=["产品经理"],
                locations=["北京"],
                skills=["Python"],
            )
        )
        updates = {
            "preferences": {
                "target_roles": ["AI产品经理"],
                "locations": ["深圳"],
                "skills": ["SQL"],
            }
        }
        result = await memory_service.merge_session_updates(current, updates, mode="merge")
        assert result.preferences.target_roles == ["产品经理", "AI产品经理"]
        assert result.preferences.locations == ["北京", "深圳"]
        assert result.preferences.skills == ["Python", "SQL"]


# ── replace 模式 ──────────────────────────────────────────────────────────

class TestReplaceMode:
    @pytest.mark.asyncio
    async def test_override_pref_list(self, memory_service):
        """replace 模式下 pref list 字段直接覆盖。"""
        current = SessionMemory(
            preferences=JobPreference(locations=["北京"])
        )
        updates = {"preferences": {"locations": ["上海"]}}
        result = await memory_service.merge_session_updates(current, updates, mode="replace")
        assert result.preferences.locations == ["上海"]

    @pytest.mark.asyncio
    async def test_open_questions_always_append(self, memory_service):
        """replace 模式下 open_questions 始终 append，不受 mode 影响。"""
        current = SessionMemory(open_questions=["Q1"])
        updates = {"open_questions": ["Q2"]}
        result = await memory_service.merge_session_updates(current, updates, mode="replace")
        assert result.open_questions == ["Q1", "Q2"]

    @pytest.mark.asyncio
    async def test_recent_decisions_always_append(self, memory_service):
        """replace 模式下 recent_decisions 始终 append。"""
        current = SessionMemory(recent_decisions=["D1"])
        updates = {"recent_decisions": ["D2"]}
        result = await memory_service.merge_session_updates(current, updates, mode="replace")
        assert result.recent_decisions == ["D1", "D2"]

    @pytest.mark.asyncio
    async def test_replace_does_not_affect_non_pref_lists(self, memory_service):
        """replace 模式不影响 open_questions/recent_decisions。"""
        current = SessionMemory(
            preferences=JobPreference(locations=["北京"]),
            open_questions=["Q1"],
            recent_decisions=["D1"],
        )
        updates = {
            "preferences": {"locations": ["上海"]},
            "open_questions": ["Q2"],
            "recent_decisions": ["D2"],
        }
        result = await memory_service.merge_session_updates(current, updates, mode="replace")
        # pref list 被覆盖
        assert result.preferences.locations == ["上海"]
        # 非 pref list 仍然 append
        assert result.open_questions == ["Q1", "Q2"]
        assert result.recent_decisions == ["D1", "D2"]


# ── 标量字段 ──────────────────────────────────────────────────────────────

class TestScalarFields:
    @pytest.mark.asyncio
    async def test_scalar_overwrite(self, memory_service):
        """标量字段（如 current_goal）直接覆盖。"""
        current = SessionMemory(current_goal="A")
        updates = {"current_goal": "B"}
        result = await memory_service.merge_session_updates(current, updates, mode="merge")
        assert result.current_goal == "B"

    @pytest.mark.asyncio
    async def test_scalar_overwrite_replace_mode(self, memory_service):
        """标量字段在 replace 模式下也直接覆盖。"""
        current = SessionMemory(current_goal="A")
        updates = {"current_goal": "C"}
        result = await memory_service.merge_session_updates(current, updates, mode="replace")
        assert result.current_goal == "C"


# ── 嵌套非 list 字段 ──────────────────────────────────────────────────────

class TestNestedNonListFields:
    @pytest.mark.asyncio
    async def test_salary_overwrite(self, memory_service):
        """嵌套非 list 字段（如 preferences.salary）直接 set。"""
        current = SessionMemory(
            preferences=JobPreference(salary=SalaryRange(min=10000))
        )
        updates = {"preferences": {"salary": SalaryRange(min=20000, max=30000)}}
        result = await memory_service.merge_session_updates(current, updates)
        assert result.preferences.salary.min == 20000
        assert result.preferences.salary.max == 30000

    @pytest.mark.asyncio
    async def test_preference_sources_overwrite(self, memory_service):
        """preference_sources dict 直接覆盖。"""
        current = SessionMemory(
            preference_sources={"locations": "user_stated"}
        )
        updates = {"preference_sources": {"locations": "agent_inferred", "salary": "user_confirmed"}}
        result = await memory_service.merge_session_updates(current, updates)
        assert result.preference_sources == {"locations": "agent_inferred", "salary": "user_confirmed"}
