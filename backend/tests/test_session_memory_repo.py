"""Unit tests for SessionMemoryRepository (mocked DB)."""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.memory.schemas import SessionMemory, JobPreference
from app.repositories.session_memory_repo import SessionMemoryRepository


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
def thread_id():
    return "thread-test-123"


class TestSessionMemoryRepository:
    @pytest.mark.asyncio
    async def test_get_by_thread_returns_none(self, mock_db, thread_id):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        repo = SessionMemoryRepository(mock_db)
        result = await repo.get_by_thread(thread_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_thread_returns_pydantic(self, mock_db, thread_id, user_id):
        from app.models.session_memory import SessionMemoryORM
        orm = SessionMemoryORM(
            id=uuid.uuid4(),
            user_id=user_id,
            thread_id=thread_id,
            preferences={"target_roles": ["AI产品经理"]},
            preference_sources={"target_roles": "user_explicit"},
            open_questions=["是否接受实习？"],
            recent_decisions=["选择北京"],
            current_goal="找AI产品岗",
            next_action="搜索岗位",
            last_updated_at=datetime(2025, 6, 1),
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = orm
        mock_db.execute.return_value = result_mock

        repo = SessionMemoryRepository(mock_db)
        result = await repo.get_by_thread(thread_id)
        assert result is not None
        assert result.current_goal == "找AI产品岗"
        assert result.preferences.target_roles == ["AI产品经理"]
        assert result.open_questions == ["是否接受实习？"]

    @pytest.mark.asyncio
    async def test_upsert_creates_new(self, mock_db, thread_id, user_id):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        payload = SessionMemory(
            current_goal="新目标",
            open_questions=["问题1"],
        )

        repo = SessionMemoryRepository(mock_db)
        await repo.upsert(thread_id, user_id, payload)

        mock_db.add.assert_called_once()
        await mock_db.flush()

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, mock_db, thread_id, user_id):
        from app.models.session_memory import SessionMemoryORM
        existing = SessionMemoryORM(
            id=uuid.uuid4(),
            user_id=user_id,
            thread_id=thread_id,
            preferences={},
            preference_sources={},
            open_questions=[],
            recent_decisions=[],
            current_goal="旧目标",
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = result_mock

        payload = SessionMemory(
            current_goal="新目标",
            open_questions=["新问题"],
            next_action="搜索",
        )

        repo = SessionMemoryRepository(mock_db)
        await repo.upsert(thread_id, user_id, payload)

        mock_db.add.assert_not_called()
        assert existing.current_goal == "新目标"
        assert existing.open_questions == ["新问题"]
        assert existing.next_action == "搜索"

    @pytest.mark.asyncio
    async def test_get_active_for_user_returns_none(self, mock_db, user_id):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        repo = SessionMemoryRepository(mock_db)
        result = await repo.get_active_for_user(user_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_for_user_returns_empty(self, mock_db, user_id):
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = result_mock

        repo = SessionMemoryRepository(mock_db)
        result = await repo.list_for_user(user_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_for_user_returns_list(self, mock_db, user_id):
        from app.models.session_memory import SessionMemoryORM
        orm1 = SessionMemoryORM(
            id=uuid.uuid4(),
            user_id=user_id,
            thread_id="t1",
            preferences={},
            preference_sources={},
            open_questions=[],
            recent_decisions=[],
            current_goal="目标1",
            last_updated_at=datetime(2025, 6, 1),
        )
        orm2 = SessionMemoryORM(
            id=uuid.uuid4(),
            user_id=user_id,
            thread_id="t2",
            preferences={},
            preference_sources={},
            open_questions=[],
            recent_decisions=[],
            current_goal="目标2",
            last_updated_at=datetime(2025, 5, 1),
        )
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [orm1, orm2]
        mock_db.execute.return_value = result_mock

        repo = SessionMemoryRepository(mock_db)
        result = await repo.list_for_user(user_id)
        assert len(result) == 2
        assert result[0].current_goal == "目标1"
        assert result[1].current_goal == "目标2"
