"""JobRepository.filter_by_hard_conditions 扩展参数单元测试。

覆盖：
- company ILIKE 模糊匹配
- city ILIKE 模糊匹配
- job_keyword ILIKE 模糊匹配
- ids 范围限定
- 多条件组合
- 无过滤条件时 early return
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, call

from app.repositories.job_repo import JobRepository


# ── helpers ────────────────────────────────────────────────────────────────

def _make_repo(rows: list | None = None):
    """构造 JobRepository，mock session.execute 返回指定行。

    rows: 模拟 fetchall() 返回的行列表，每行是 (uuid_value,) 元组。
    """
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows or []
    session.execute = AsyncMock(return_value=mock_result)
    return JobRepository(session), session


# ── 无过滤条件 early return ────────────────────────────────────────────────

class TestEarlyReturn:
    async def test_no_filters_returns_empty(self):
        """所有参数都为 None 时直接返回空列表，不执行 SQL。"""
        repo, session = _make_repo()
        result = await repo.filter_by_hard_conditions()
        assert result == []
        session.execute.assert_not_called()

    async def test_empty_strings_return_empty(self):
        """所有参数都是空字符串/空列表时直接返回空列表。"""
        repo, session = _make_repo()
        result = await repo.filter_by_hard_conditions(
            recruitment_types=[], company="", city="", job_keyword=""
        )
        assert result == []
        session.execute.assert_not_called()


# ── company 模糊匹配 ──────────────────────────────────────────────────────

class TestCompanyFilter:
    async def test_company_triggers_query(self):
        """传 company 参数时应执行 SQL 查询。"""
        repo, session = _make_repo()
        await repo.filter_by_hard_conditions(company="字节")
        session.execute.assert_called_once()

    async def test_company_returns_ids(self):
        """company 过滤返回匹配的 job id 字符串列表。"""
        id1 = uuid.uuid4()
        id2 = uuid.uuid4()
        repo, session = _make_repo(rows=[(id1,), (id2,)])
        result = await repo.filter_by_hard_conditions(company="字节")
        assert result == [str(id1), str(id2)]


# ── city 模糊匹配 ─────────────────────────────────────────────────────────

class TestCityFilter:
    async def test_city_triggers_query(self):
        """传 city 参数时应执行 SQL 查询。"""
        repo, session = _make_repo()
        await repo.filter_by_hard_conditions(city="深圳")
        session.execute.assert_called_once()

    async def test_city_returns_ids(self):
        """city 过滤返回匹配的 job id 字符串列表。"""
        id1 = uuid.uuid4()
        repo, session = _make_repo(rows=[(id1,)])
        result = await repo.filter_by_hard_conditions(city="深圳")
        assert result == [str(id1)]


# ── job_keyword 模糊匹配 ──────────────────────────────────────────────────

class TestJobKeywordFilter:
    async def test_job_keyword_triggers_query(self):
        """传 job_keyword 参数时应执行 SQL 查询。"""
        repo, session = _make_repo()
        await repo.filter_by_hard_conditions(job_keyword="算法")
        session.execute.assert_called_once()

    async def test_job_keyword_returns_ids(self):
        """job_keyword 过滤返回匹配的 job id 字符串列表。"""
        id1 = uuid.uuid4()
        repo, session = _make_repo(rows=[(id1,)])
        result = await repo.filter_by_hard_conditions(job_keyword="算法")
        assert result == [str(id1)]


# ── ids 范围限定 ──────────────────────────────────────────────────────────

class TestIdsFilter:
    async def test_ids_triggers_query(self):
        """传 ids 参数时应执行 SQL 查询。"""
        repo, session = _make_repo()
        test_id = str(uuid.uuid4())
        await repo.filter_by_hard_conditions(ids=[test_id])
        session.execute.assert_called_once()

    async def test_ids_returns_matching_ids(self):
        """ids 过滤返回在范围内的 job id。"""
        id1 = uuid.uuid4()
        id2 = uuid.uuid4()
        repo, session = _make_repo(rows=[(id1,), (id2,)])
        result = await repo.filter_by_hard_conditions(ids=[str(id1), str(id2)])
        assert len(result) == 2
        assert str(id1) in result
        assert str(id2) in result


# ── 多条件组合 ─────────────────────────────────────────────────────────────

class TestCombinedFilters:
    async def test_company_and_city(self):
        """company + city 组合过滤。"""
        id1 = uuid.uuid4()
        repo, session = _make_repo(rows=[(id1,)])
        result = await repo.filter_by_hard_conditions(company="字节", city="深圳")
        session.execute.assert_called_once()
        assert result == [str(id1)]

    async def test_company_city_and_keyword(self):
        """company + city + job_keyword 三组合。"""
        id1 = uuid.uuid4()
        repo, session = _make_repo(rows=[(id1,)])
        result = await repo.filter_by_hard_conditions(
            company="字节", city="深圳", job_keyword="算法"
        )
        session.execute.assert_called_once()
        assert result == [str(id1)]

    async def test_ids_with_company(self):
        """ids + company 组合（后置过滤场景）。"""
        id1 = uuid.uuid4()
        repo, session = _make_repo(rows=[(id1,)])
        result = await repo.filter_by_hard_conditions(
            ids=[str(id1)], company="字节"
        )
        session.execute.assert_called_once()
        assert result == [str(id1)]

    async def test_all_new_params_combined(self):
        """company + city + job_keyword + ids 四组合。"""
        id1 = uuid.uuid4()
        repo, session = _make_repo(rows=[(id1,)])
        result = await repo.filter_by_hard_conditions(
            company="字节", city="深圳", job_keyword="算法", ids=[str(id1)]
        )
        session.execute.assert_called_once()
        assert result == [str(id1)]

    async def test_no_match_returns_empty(self):
        """所有条件都不匹配时返回空列表。"""
        repo, session = _make_repo(rows=[])
        result = await repo.filter_by_hard_conditions(company="不存在的公司")
        assert result == []
