"""JobMatchingService 单元测试。

覆盖 Phase 2（全后置架构 + 纯 SQL 降级）和 Phase 3（L2 向量召回缓存）。

Phase 2:
- 有 expanded_query + 有 hard_filters → 向量召回 + 后置过滤
- 无 expanded_query + 有 hard_filters → 纯 SQL 查询
- 无 expanded_query + 无 hard_filters → 返回空
- 纯精确搜索 score=0.0

Phase 3:
- 缓存命中（相同 expanded_query + top_k）
- 缓存未命中（expanded_query 变化）
- TTL 过期失效
- hard_filters 变化不影响缓存命中
"""
import uuid
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.job_matching_service import JobMatchingService


# ── fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_cache():
    """每个测试前清空 L2 缓存。"""
    JobMatchingService._recall_cache.clear()
    yield
    JobMatchingService._recall_cache.clear()


@pytest.fixture
def service():
    """构造 JobMatchingService（mock LLM 和向量库）。"""
    with patch("app.services.job_matching_service.LLMService") as mock_llm_cls, \
         patch("app.services.job_matching_service.VectorDBService") as mock_vdb_cls:
        svc = JobMatchingService()
        svc.llm_service.generate_embedding = AsyncMock(return_value=[0.1] * 768)
        svc.vector_db_service = MagicMock()
        return svc


def _make_job_repo():
    """构造 mock JobRepository。"""
    repo = AsyncMock()
    repo.filter_by_hard_conditions = AsyncMock(return_value=[])
    repo.get_by_ids = AsyncMock(return_value=[])
    return repo


def _make_mock_job(job_id=None, title="测试岗位", company="测试公司"):
    """构造 mock JobItem 对象。"""
    job = MagicMock()
    job.id = job_id or uuid.uuid4()
    job.job_title = title
    job.company_name = company
    job.location = "深圳"
    job.update_time = None
    return job


def _make_raw_results(n=3):
    """构造 Milvus 模拟返回结果。"""
    return [
        {"id": str(uuid.uuid4()), "distance": 0.9 - i * 0.1}
        for i in range(n)
    ]


# ── Phase 2: 纯 SQL 降级 ──────────────────────────────────────────────────

class TestPureSQLFallback:
    async def test_no_query_no_filters_returns_empty(self, service):
        """无 expanded_query + 无 hard_filters → 返回空。"""
        result = await service.match_jobs(
            user_query_preference={},
            user_resume_profile={},
            hard_filters={},
            job_repo=_make_job_repo(),
        )
        assert result == []

    async def test_no_query_with_filters_pure_sql(self, service):
        """无 expanded_query + 有 hard_filters → 纯 SQL 查询。"""
        job_repo = _make_job_repo()
        job_id = uuid.uuid4()
        mock_job = _make_mock_job(job_id=job_id)

        job_repo.filter_by_hard_conditions.return_value = [str(job_id)]
        job_repo.get_by_ids.return_value = [mock_job]

        result = await service.match_jobs(
            user_query_preference={},
            user_resume_profile={},
            hard_filters={"company": "字节"},
            job_repo=job_repo,
        )

        # 纯 SQL 路径不调用 LLM/Milvus
        service.llm_service.generate_embedding.assert_not_called()
        service.vector_db_service.search_hybrid.assert_not_called()

        # 返回 score=0.0
        assert len(result) == 1
        assert result[0]["score"] == 0.0
        assert result[0]["job_item"] == mock_job

    async def test_pure_sql_no_match_returns_empty(self, service):
        """纯 SQL 路径无匹配时返回空。"""
        job_repo = _make_job_repo()
        job_repo.filter_by_hard_conditions.return_value = []

        result = await service.match_jobs(
            user_query_preference={},
            user_resume_profile={},
            hard_filters={"company": "不存在"},
            job_repo=job_repo,
        )
        assert result == []


# ── Phase 2: 全后置架构 ───────────────────────────────────────────────────

class TestPostFilterArchitecture:
    async def test_vector_recall_with_post_filter(self, service):
        """有 expanded_query + 有 hard_filters → Milvus 裸召回 + 后置过滤。"""
        job_repo = _make_job_repo()
        raw_results = _make_raw_results(3)

        # Milvus 返回 3 条
        service.vector_db_service.search_hybrid.return_value = raw_results

        # 后置过滤只保留第 1 条
        hit_ids = [r["id"] for r in raw_results]
        job_repo.filter_by_hard_conditions.return_value = [hit_ids[0]]

        result = await service.match_jobs(
            user_query_preference={"keywords": "算法工程师"},
            user_resume_profile={},
            hard_filters={"company": "字节"},
            job_repo=job_repo,
        )

        # 验证 Milvus 使用空 filter_expr（裸召回）
        call_kwargs = service.vector_db_service.search_hybrid.call_args
        assert call_kwargs.kwargs.get("filter_expr", call_kwargs[1].get("filter_expr", "")) == ""

        # 验证后置过滤被调用（带 ids 参数）
        job_repo.filter_by_hard_conditions.assert_called_once()
        call_kwargs = job_repo.filter_by_hard_conditions.call_args
        assert "ids" in call_kwargs.kwargs or (call_kwargs[1] and "ids" in call_kwargs[1])

    async def test_vector_recall_no_filters_skips_post_filter(self, service):
        """有 expanded_query + 无 hard_filters → 跳过置过滤。"""
        job_repo = _make_job_repo()
        raw_results = _make_raw_results(2)

        service.vector_db_service.search_hybrid.return_value = raw_results

        result = await service.match_jobs(
            user_query_preference={"keywords": "算法工程师"},
            user_resume_profile={},
            hard_filters=None,
            job_repo=job_repo,
        )

        # 无 hard_filters 时，后置过滤不应被调用
        job_repo.filter_by_hard_conditions.assert_not_called()

    async def test_filter_expr_is_empty_for_all_modes(self, service):
        """三种搜索 filter_expr 都为空字符串。"""
        job_repo = _make_job_repo()

        for mode in ["semantic", "sparse", "hybrid"]:
            service.vector_db_service.search_semantic.return_value = _make_raw_results(1)
            service.vector_db_service.search_sparse.return_value = _make_raw_results(1)
            service.vector_db_service.search_hybrid.return_value = _make_raw_results(1)

            JobMatchingService._recall_cache.clear()

            await service.match_jobs(
                user_query_preference={"keywords": "测试"},
                user_resume_profile={},
                search_mode=mode,
                job_repo=job_repo,
            )

            # 验证对应的搜索方法被调用且 filter_expr=""
            if mode == "semantic":
                call_args = service.vector_db_service.search_semantic.call_args
                assert call_args.kwargs.get("filter_expr", "") == ""
            elif mode == "sparse":
                call_args = service.vector_db_service.search_sparse.call_args
                assert call_args.kwargs.get("filter_expr", "") == ""
            elif mode == "hybrid":
                call_args = service.vector_db_service.search_hybrid.call_args
                assert call_args.kwargs.get("filter_expr", "") == ""


# ── Phase 3: L2 向量召回缓存 ──────────────────────────────────────────────

class TestL2RecallCache:
    async def test_cache_hit_skips_milvus(self, service):
        """相同 expanded_query + top_k → 缓存命中，跳过 Milvus。"""
        job_repo = _make_job_repo()
        raw_results = _make_raw_results(2)

        service.vector_db_service.search_hybrid.return_value = raw_results

        # 第一次调用：缓存未命中
        await service.match_jobs(
            user_query_preference={"keywords": "算法工程师"},
            user_resume_profile={},
            job_repo=job_repo,
        )
        assert service.vector_db_service.search_hybrid.call_count == 1

        # 第二次调用：相同 query → 缓存命中
        await service.match_jobs(
            user_query_preference={"keywords": "算法工程师"},
            user_resume_profile={},
            job_repo=job_repo,
        )
        # Milvus 不应被第二次调用
        assert service.vector_db_service.search_hybrid.call_count == 1

    async def test_cache_miss_on_different_query(self, service):
        """不同 expanded_query → 缓存未命中，重新调用 Milvus。"""
        job_repo = _make_job_repo()
        service.vector_db_service.search_hybrid.return_value = _make_raw_results(1)

        # 第一次
        await service.match_jobs(
            user_query_preference={"keywords": "算法工程师"},
            user_resume_profile={},
            job_repo=job_repo,
        )
        assert service.vector_db_service.search_hybrid.call_count == 1

        # 第二次：不同 query
        await service.match_jobs(
            user_query_preference={"keywords": "前端开发"},
            user_resume_profile={},
            job_repo=job_repo,
        )
        assert service.vector_db_service.search_hybrid.call_count == 2

    async def test_cache_ttl_expiry(self, service):
        """TTL 过期后缓存失效。"""
        job_repo = _make_job_repo()
        service.vector_db_service.search_hybrid.return_value = _make_raw_results(1)

        # 第一次调用，写入缓存
        await service.match_jobs(
            user_query_preference={"keywords": "算法工程师"},
            user_resume_profile={},
            job_repo=job_repo,
        )
        assert service.vector_db_service.search_hybrid.call_count == 1

        # 手动让缓存过期
        for key in JobMatchingService._recall_cache:
            JobMatchingService._recall_cache[key]["ts"] = time.time() - 700  # 超过 600s TTL

        # 第二次调用：缓存已过期
        await service.match_jobs(
            user_query_preference={"keywords": "算法工程师"},
            user_resume_profile={},
            job_repo=job_repo,
        )
        assert service.vector_db_service.search_hybrid.call_count == 2

    async def test_hard_filters_change_does_not_miss_cache(self, service):
        """hard_filters 变化不影响 L2 缓存命中（key 不含 hard_filters）。"""
        job_repo = _make_job_repo()
        service.vector_db_service.search_hybrid.return_value = _make_raw_results(2)

        # 第一次：无 hard_filters
        await service.match_jobs(
            user_query_preference={"keywords": "算法工程师"},
            user_resume_profile={},
            hard_filters={},
            job_repo=job_repo,
        )
        assert service.vector_db_service.search_hybrid.call_count == 1

        # 第二次：加了 hard_filters → 向量召回部分应命中缓存
        await service.match_jobs(
            user_query_preference={"keywords": "算法工程师"},
            user_resume_profile={},
            hard_filters={"company": "字节"},
            job_repo=job_repo,
        )
        # Milvus 不应被第二次调用
        assert service.vector_db_service.search_hybrid.call_count == 1


# ── _build_recall_key ─────────────────────────────────────────────────────

class TestBuildRecallKey:
    def test_same_input_same_key(self, service):
        """相同输入生成相同 key。"""
        key1 = service._build_recall_key("算法工程师", 100)
        key2 = service._build_recall_key("算法工程师", 100)
        assert key1 == key2

    def test_different_query_different_key(self, service):
        """不同 query 生成不同 key。"""
        key1 = service._build_recall_key("算法工程师", 100)
        key2 = service._build_recall_key("前端开发", 100)
        assert key1 != key2

    def test_different_top_k_different_key(self, service):
        """不同 top_k 生成不同 key。"""
        key1 = service._build_recall_key("算法工程师", 100)
        key2 = service._build_recall_key("算法工程师", 50)
        assert key1 != key2

    def test_key_contains_md5_and_top_k(self, service):
        """key 格式：md5_hash|top_k。"""
        key = service._build_recall_key("测试", 100)
        assert "|100" in key
        assert "|" in key


# ── _get_cached_recall / _set_cached_recall ───────────────────────────────

class TestCacheOperations:
    def test_set_and_get(self, service):
        """写入缓存后可读取。"""
        key = "test_key"
        results = [{"id": "1", "distance": 0.9}]
        service._set_cached_recall(key, results)
        cached = service._get_cached_recall(key)
        assert cached == results

    def test_get_nonexistent_returns_none(self, service):
        """不存在的 key 返回 None。"""
        assert service._get_cached_recall("nonexistent") is None

    def test_expired_entry_returns_none(self, service):
        """过期条目返回 None。"""
        key = "test_key"
        service._set_cached_recall(key, [{"id": "1"}])
        # 手动过期
        JobMatchingService._recall_cache[key]["ts"] = time.time() - 700
        assert service._get_cached_recall(key) is None

    def test_expired_entry_is_deleted(self, service):
        """过期条目被从缓存中删除。"""
        key = "test_key"
        service._set_cached_recall(key, [{"id": "1"}])
        JobMatchingService._recall_cache[key]["ts"] = time.time() - 700
        service._get_cached_recall(key)
        assert key not in JobMatchingService._recall_cache
