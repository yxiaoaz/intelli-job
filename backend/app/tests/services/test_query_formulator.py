"""QueryFormulator 单元测试。

覆盖：
- _extract_role_from_query 规则抽取
- _build_cache_key 缓存 key 构建
- _resolve_target_role 三路信号解析
- formulate 主入口（缓存命中 / 降级 / 三路空）
- _degrade_to_s1 降级输出
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.query_formulator import QueryFormulator
from app.memory.schemas import JobPreference, UserMemory, SalaryRange


# ── fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def formulator():
    """构造 QueryFormulator（不触发真实 LLM 初始化）。"""
    with patch("app.services.query_formulator.LLMService"):
        return QueryFormulator()


@pytest.fixture(autouse=True)
def clear_cache():
    """每个测试前清空类级缓存。"""
    QueryFormulator._shared_cache.clear()
    yield
    QueryFormulator._shared_cache.clear()


# ── _extract_role_from_query ──────────────────────────────────────────────

class TestExtractRoleFromQuery:
    def test_product_manager(self):
        result = QueryFormulator._extract_role_from_query("产品经理")
        assert result == "产品经理"

    def test_java_backend_engineer(self):
        result = QueryFormulator._extract_role_from_query("Java后端工程师")
        assert "工程师" in result

    def test_short_text_fallback(self):
        """短文本（<=10字）无匹配时直接返回。"""
        result = QueryFormulator._extract_role_from_query("搞数据的")
        assert result == "搞数据的"

    def test_empty_string(self):
        result = QueryFormulator._extract_role_from_query("")
        assert result is None

    def test_long_text_no_match(self):
        result = QueryFormulator._extract_role_from_query(
            "我想找一份能够充分发挥我的数据分析能力和项目管理经验的工作"
        )
        assert result is None

    def test_senior_ai_engineer(self):
        result = QueryFormulator._extract_role_from_query("资深AI算法工程师")
        # pattern 2 (工程师) 先于 pattern 3 (算法工程师) 匹配
        assert "工程师" in result

    def test_ui_designer(self):
        result = QueryFormulator._extract_role_from_query("高级UI设计师")
        assert "UI设计师" in result


# ── _build_cache_key ──────────────────────────────────────────────────────

class TestBuildCacheKey:
    def test_same_input_same_key(self):
        prefs = JobPreference(target_roles=["产品经理"], locations=["深圳"])
        key1 = QueryFormulator._build_cache_key("产品经理", prefs, {}, "r1")
        key2 = QueryFormulator._build_cache_key("产品经理", prefs, {}, "r1")
        assert key1 == key2

    def test_different_resume_id_different_key(self):
        prefs = JobPreference(target_roles=["产品经理"])
        key1 = QueryFormulator._build_cache_key("产品经理", prefs, {}, "r1")
        key2 = QueryFormulator._build_cache_key("产品经理", prefs, {}, "r2")
        assert key1 != key2

    def test_no_resume_id(self):
        prefs = JobPreference()
        key = QueryFormulator._build_cache_key("test", prefs, {})
        assert key.endswith("|")  # resume_id 为空时末尾是 |

    def test_salary_in_key(self):
        prefs = JobPreference(salary=SalaryRange(min=20000))
        key = QueryFormulator._build_cache_key("test", prefs, {})
        assert "sal:20000" in key


# ── _resolve_target_role ──────────────────────────────────────────────────

class TestResolveTargetRole:
    def test_preferences_priority(self, formulator):
        """preferences.target_roles 有值时优先返回。"""
        prefs = JobPreference(target_roles=["产品经理"])
        result = formulator._resolve_target_role("随便搜", prefs, None)
        assert result == "产品经理"

    def test_query_extraction_fallback(self, formulator):
        """preferences 空时从 query 抽取。"""
        prefs = JobPreference()
        result = formulator._resolve_target_role("Java后端工程师", prefs, None)
        assert "工程师" in result

    def test_career_direction_fallback(self, formulator):
        """前两者空时用 user_memory.career_direction。"""
        prefs = JobPreference()
        user_mem = UserMemory(career_direction="AI产品经理方向")
        # 用 >10 字的长文本，避免触发短文本兜底
        long_query = "我想找一份能够充分发挥我的数据分析能力和项目管理经验的工作"
        result = formulator._resolve_target_role(long_query, prefs, user_mem)
        assert result == "AI产品经理方向"

    def test_all_three_empty(self, formulator):
        """三路都空返回 None。"""
        prefs = JobPreference()
        user_mem = UserMemory()  # career_direction=None
        result = formulator._resolve_target_role(
            "我想找一份能够充分发挥我的数据分析能力和项目管理经验的工作",
            prefs,
            user_mem,
        )
        assert result is None


# ── formulate (async) ─────────────────────────────────────────────────────

class TestFormulate:
    @pytest.mark.asyncio
    async def test_all_three_signals_empty(self, formulator):
        """三路信号都空 → 不调 LLM，返回原始 query。"""
        prefs = JobPreference()
        user_mem = UserMemory()
        result = await formulator.formulate(
            natural_query="我想找一份能够充分发挥我的数据分析能力和项目管理经验的工作",
            session_preferences=prefs,
            user_memory=user_mem,
        )
        assert result["expanded_query"] == "我想找一份能够充分发挥我的数据分析能力和项目管理经验的工作"
        assert result["synonyms"] == []
        assert result["original_keywords"] == "我想找一份能够充分发挥我的数据分析能力和项目管理经验的工作"

    @pytest.mark.asyncio
    async def test_cache_hit(self, formulator):
        """缓存命中时不调 LLM，直接返回缓存结果。"""
        prefs = JobPreference(target_roles=["产品经理"])

        # 预填缓存
        cache_key = QueryFormulator._build_cache_key("产品经理", prefs, {}, None)
        cached_result = {
            "expanded_query": "cached_expanded",
            "synonyms": ["cached_syn"],
            "original_keywords": "产品经理",
        }
        QueryFormulator._shared_cache[cache_key] = cached_result

        result = await formulator.formulate(
            natural_query="产品经理",
            session_preferences=prefs,
        )
        assert result == cached_result

    @pytest.mark.asyncio
    async def test_llm_failure_degrades(self, formulator):
        """LLM 调用失败时降级为 S1 机械拼接。"""
        formulator._call_llm = AsyncMock(side_effect=Exception("LLM down"))

        prefs = JobPreference(target_roles=["产品经理"], locations=["深圳"])
        resume = {"skills": ["Python", "SQL"]}

        result = await formulator.formulate(
            natural_query="产品经理",
            session_preferences=prefs,
            resume_profile=resume,
        )
        # 降级输出应包含 keywords
        assert "keywords: 产品经理" in result["expanded_query"]
        assert "target_roles: 产品经理" in result["expanded_query"]
        assert result["synonyms"] == []
        assert result["original_keywords"] == "产品经理"

    @pytest.mark.asyncio
    async def test_llm_success_caches_result(self, formulator):
        """LLM 成功后结果写入缓存。"""
        formulator._call_llm = AsyncMock(return_value={
            "expanded_query": "负责B端产品规划",
            "synonyms": ["PM"],
        })

        prefs = JobPreference(target_roles=["产品经理"])

        result = await formulator.formulate(
            natural_query="产品经理",
            session_preferences=prefs,
        )
        assert result["expanded_query"] == "负责B端产品规划"
        assert result["original_keywords"] == "产品经理"

        # 验证缓存已写入
        cache_key = QueryFormulator._build_cache_key("产品经理", prefs, {}, None)
        assert cache_key in QueryFormulator._shared_cache


# ── _degrade_to_s1 ────────────────────────────────────────────────────────

class TestDegradeToS1:
    def test_basic_output(self):
        prefs = JobPreference(target_roles=["产品经理"], locations=["深圳"])
        resume = {"skills": ["Python", "SQL"], "latest_title": "PM", "latest_company": "字节"}

        result = QueryFormulator._degrade_to_s1("产品经理", prefs, resume)

        assert "keywords: 产品经理" in result["expanded_query"]
        assert "target_roles: 产品经理" in result["expanded_query"]
        assert "locations: 深圳" in result["expanded_query"]
        assert "skills: Python, SQL" in result["expanded_query"]
        assert "最近职位: PM @ 字节" in result["expanded_query"]
        assert result["synonyms"] == []

    def test_empty_inputs(self):
        prefs = JobPreference()
        result = QueryFormulator._degrade_to_s1("test", prefs, {})
        assert "keywords: test" in result["expanded_query"]
        assert result["synonyms"] == []
