"""Unit tests for UserMemoryRepository (mocked DB)."""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.memory.schemas import UserMemory, JobPreference, SalaryRange
from app.repositories.user_memory_repo import UserMemoryRepository


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def sample_preference():
    return JobPreference(
        target_roles=["产品经理"],
        locations=["深圳"],
        salary=SalaryRange(min=15000, max=25000),
        target_companies=["字节"],
        target_company_types=["大厂"],
        industries=["AI"],
        recruitment_types=["EXPERIENCED"],
        skills=["Python"],
    )


class TestUserMemoryRepository:
    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, mock_db, user_id):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        repo = UserMemoryRepository(mock_db)
        result = await repo.get(user_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_pydantic(self, mock_db, user_id):
        from app.models.user_memory import UserMemoryORM
        orm = UserMemoryORM(
            user_id=user_id,
            stable_facts={"name": "测试"},
            long_term_preferences={"target_roles": ["产品经理"]},
            negative_signals=[],
            career_direction="AI方向",
            last_updated_at=datetime(2025, 1, 1),
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = orm
        mock_db.execute.return_value = result_mock

        repo = UserMemoryRepository(mock_db)
        result = await repo.get(user_id)
        assert result is not None
        assert result.stable_facts == {"name": "测试"}
        assert result.long_term_preferences.target_roles == ["产品经理"]
        assert result.career_direction == "AI方向"

    @pytest.mark.asyncio
    async def test_upsert_creates_new(self, mock_db, user_id, sample_preference):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        payload = UserMemory(
            stable_facts={"name": "新"},
            long_term_preferences=sample_preference,
            negative_signals=["不做销售"],
            career_direction="AI方向",
        )

        repo = UserMemoryRepository(mock_db)
        await repo.upsert(user_id, payload)

        mock_db.add.assert_called_once()
        await mock_db.flush()

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, mock_db, user_id, sample_preference):
        from app.models.user_memory import UserMemoryORM
        existing = UserMemoryORM(
            user_id=user_id,
            stable_facts={},
            long_term_preferences={},
            negative_signals=[],
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = result_mock

        payload = UserMemory(
            stable_facts={"name": "更新"},
            long_term_preferences=sample_preference,
        )

        repo = UserMemoryRepository(mock_db)
        await repo.upsert(user_id, payload)

        mock_db.add.assert_not_called()  # 不应创建新的
        assert existing.stable_facts == {"name": "更新"}
        assert existing.long_term_preferences["target_roles"] == ["产品经理"]

    @pytest.mark.asyncio
    async def test_get_preferences_returns_none(self, mock_db, user_id):
        result_mock = MagicMock()
        result_mock.one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        repo = UserMemoryRepository(mock_db)
        result = await repo.get_preferences(user_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_preferences_returns_job_preference(self, mock_db, user_id):
        prefs_data = {"target_roles": ["产品经理"], "locations": ["深圳"]}
        result_mock = MagicMock()
        result_mock.one_or_none.return_value = (prefs_data,)
        mock_db.execute.return_value = result_mock

        repo = UserMemoryRepository(mock_db)
        result = await repo.get_preferences(user_id)
        assert result is not None
        assert result.target_roles == ["产品经理"]
        assert result.locations == ["深圳"]
