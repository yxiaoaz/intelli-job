"""Integration tests for memory system full flow.

Tests cover:
- L1 write-through (markdown + DB dual write)
- L2 只写 DB（agent-context-overhaul Phase 3.1：profile.md 投影已退役）
- chat_end_reconcile (markdown newer than DB → sync)
- Merge logic (list append / scalar set / nested JobPreference)
- L2 写入来源仲裁 merge_with_source（Phase 3.3）
"""
import os
import json
import uuid
import tempfile
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.memory.schemas import (
    UserMemory,
    SessionMemory,
    JobPreference,
    SalaryRange,
)
from app.memory.service import MemoryService
from app.memory.markdown_renderer import (
    render_user_memory,
    render_session_memory,
    parse_session_memory,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def thread_id():
    return "test-thread-001"


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_job_pref():
    return JobPreference(
        target_roles=["产品经理"],
        locations=["深圳", "广州"],
        salary=SalaryRange(min=15000, max=25000),
        recruitment_types=["EXPERIENCED"],
        industries=["互联网"],
        skills=["Python", "React"],
        target_companies=["字节"],
        target_company_types=["大厂"],
    )


@pytest.fixture
def sample_session_memory(sample_job_pref):
    return SessionMemory(
        current_goal="找深圳产品经理岗",
        preferences=sample_job_pref,
        preference_sources={"locations": "user_stated"},
        open_questions=["是否接受广州？"],
        recent_decisions=["聚焦深圳"],
        next_action="搜索匹配岗位",
        last_updated=datetime.utcnow(),
    )


@pytest.fixture
def sample_user_memory(sample_job_pref):
    return UserMemory(
        long_term_preferences=sample_job_pref,
        preference_sources={"locations": "user", "target_roles": "resume"},
        negative_signals=["不做销售"],
        career_direction="AI 产品方向",
        last_updated=datetime.utcnow(),
    )


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


# ── Scenario A: MemoryService 写入语义 ───────────────────────────────


class TestWriteThrough:
    """验证 markdown + DB 双写一致性"""

    @pytest.mark.asyncio
    async def test_write_session_memory_creates_markdown_and_calls_db(
        self, mock_db, tmp_dir, user_id, thread_id, sample_session_memory
    ):
        """write_session_memory 应同时写 markdown 文件和 DB"""
        with patch("app.memory.service.SessionMemoryRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.upsert = AsyncMock()

            service = MemoryService(mock_db, base_dir=tmp_dir)
            await service.write_session_memory(user_id, thread_id, sample_session_memory)

            # 1. markdown 文件已创建
            md_path = tmp_dir / f"user-{user_id}" / f"session-{thread_id}.md"
            assert md_path.exists(), "markdown 文件应该被创建"
            content = md_path.read_text(encoding="utf-8")
            assert "找深圳产品经理岗" in content
            assert "target_roles" in content

            # 2. DB upsert 被调用
            repo_instance.upsert.assert_awaited_once()

            # 3. commit 被调用
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_write_user_memory_writes_db_only(
        self, mock_db, tmp_dir, user_id, sample_user_memory
    ):
        """L2 只写 DB，不再落盘 profile.md（Phase 3.1）"""
        with patch("app.memory.service.UserMemoryRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.upsert = AsyncMock()

            service = MemoryService(mock_db, base_dir=tmp_dir)
            await service.write_user_memory(user_id, sample_user_memory)

            # 1. DB upsert 被调用
            repo_instance.upsert.assert_awaited_once()
            mock_db.commit.assert_awaited_once()

            # 2. 不得生成任何磁盘投影
            profile_path = tmp_dir / f"user-{user_id}" / "profile.md"
            assert not profile_path.exists(), "L2 已不落盘，/memory/profile.md 由 DbBackend 渲染"

    @pytest.mark.asyncio
    async def test_write_user_memory_db_failure_raises(
        self, mock_db, tmp_dir, user_id, sample_user_memory
    ):
        """L2 唯一真理源，写库失败必须上抛（不能像 L1 那样只 warning 继续）"""
        with patch("app.memory.service.UserMemoryRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.upsert = AsyncMock(side_effect=Exception("DB error"))

            service = MemoryService(mock_db, base_dir=tmp_dir)
            with pytest.raises(Exception, match="DB error"):
                await service.write_user_memory(user_id, sample_user_memory)

    @pytest.mark.asyncio
    async def test_write_session_db_failure_still_creates_markdown(
        self, mock_db, tmp_dir, user_id, thread_id, sample_session_memory
    ):
        """DB 写失败时 markdown 仍然已创建（不阻塞）"""
        with patch("app.memory.service.SessionMemoryRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.upsert = AsyncMock(side_effect=Exception("DB error"))

            service = MemoryService(mock_db, base_dir=tmp_dir)
            # 不应抛异常
            await service.write_session_memory(user_id, thread_id, sample_session_memory)

            # markdown 仍然被创建
            md_path = tmp_dir / f"user-{user_id}" / f"session-{thread_id}.md"
            assert md_path.exists()


# ── Scenario B: Reconcile 兜底 ────────────────────────────────────────────


class TestReconcile:
    """验证 chat_end_reconcile 的同步逻辑"""

    @pytest.mark.asyncio
    async def test_reconcile_creates_db_record_when_missing(
        self, mock_db, tmp_dir, user_id, thread_id, sample_session_memory
    ):
        """DB 无记录时，从 markdown 创建"""
        from app.memory.reconcile import chat_end_reconcile

        # 1. 先写 markdown 文件
        user_dir = tmp_dir / f"user-{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        md_path = user_dir / f"session-{thread_id}.md"
        md_content = render_session_memory(sample_session_memory)
        md_path.write_text(md_content, encoding="utf-8")

        with patch("app.memory.reconcile.SessionMemoryRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            # DB 无记录
            repo_instance.get_by_thread = AsyncMock(return_value=None)
            repo_instance.upsert = AsyncMock()

            await chat_end_reconcile(mock_db, user_id, thread_id, str(md_path))

            # upsert 被调用（从 markdown 创建）
            repo_instance.upsert.assert_awaited_once()
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reconcile_updates_when_markdown_newer(
        self, mock_db, tmp_dir, user_id, thread_id, sample_session_memory
    ):
        """markdown 比 DB 新时触发更新"""
        from app.memory.reconcile import chat_end_reconcile

        # 1. 写 markdown
        user_dir = tmp_dir / f"user-{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        md_path = user_dir / f"session-{thread_id}.md"
        md_path.write_text(render_session_memory(sample_session_memory), encoding="utf-8")

        # 2. DB 记录比 markdown 旧
        old_record = SessionMemory(
            current_goal="旧目标",
            last_updated=datetime.utcnow() - timedelta(hours=1),
        )

        with patch("app.memory.reconcile.SessionMemoryRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_by_thread = AsyncMock(return_value=old_record)
            repo_instance.upsert = AsyncMock()

            await chat_end_reconcile(mock_db, user_id, thread_id, str(md_path))

            # 应该触发更新
            repo_instance.upsert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reconcile_skips_when_db_newer(
        self, mock_db, tmp_dir, user_id, thread_id, sample_session_memory
    ):
        """DB 比 markdown 新时跳过"""
        from app.memory.reconcile import chat_end_reconcile

        # 1. 写 markdown
        user_dir = tmp_dir / f"user-{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        md_path = user_dir / f"session-{thread_id}.md"
        md_path.write_text(render_session_memory(sample_session_memory), encoding="utf-8")

        # 2. DB 记录比 markdown 新（用足够大的时间差避免 Windows 文件时间精度问题）
        new_record = SessionMemory(
            current_goal="新目标",
            last_updated=datetime(2099, 1, 1),
        )

        with patch("app.memory.reconcile.SessionMemoryRepository") as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_by_thread = AsyncMock(return_value=new_record)
            repo_instance.upsert = AsyncMock()

            await chat_end_reconcile(mock_db, user_id, thread_id, str(md_path))

            # 不应触发更新
            repo_instance.upsert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reconcile_noop_when_markdown_missing(
        self, mock_db, tmp_dir, user_id, thread_id
    ):
        """markdown 文件不存在时直接返回"""
        from app.memory.reconcile import chat_end_reconcile

        fake_path = str(tmp_dir / "nonexistent.md")
        # 不应抛异常
        await chat_end_reconcile(mock_db, user_id, thread_id, fake_path)


# ── Scenario C: Merge logic ──────────────────────────────────────────────


class TestMergeLogic:
    """验证粗粒度 merge 语义"""

    @pytest.mark.asyncio
    async def test_session_merge_list_append_dedup(self, mock_db, tmp_dir):
        """list 字段 append 去重"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = SessionMemory(
            open_questions=["Q1", "Q2"],
            recent_decisions=["D1"],
        )
        updates = {
            "open_questions": ["Q2", "Q3"],  # Q2 重复
            "recent_decisions": ["D1", "D2"],  # D1 重复
        }
        merged = await service.merge_session_updates(current, updates)

        assert merged.open_questions == ["Q1", "Q2", "Q3"]
        assert merged.recent_decisions == ["D1", "D2"]

    @pytest.mark.asyncio
    async def test_session_merge_scalar_set(self, mock_db, tmp_dir):
        """标量字段直接覆盖"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = SessionMemory(current_goal="旧目标", next_action="旧动作")
        updates = {"current_goal": "新目标", "next_action": "新动作"}
        merged = await service.merge_session_updates(current, updates)

        assert merged.current_goal == "新目标"
        assert merged.next_action == "新动作"

    @pytest.mark.asyncio
    async def test_session_merge_nested_preferences(self, mock_db, tmp_dir):
        """preferences 嵌套 merge: list append, scalar set"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = SessionMemory(
            preferences=JobPreference(
                target_roles=["产品经理"],
                locations=["深圳"],
            )
        )
        updates = {
            "preferences": {
                "target_roles": ["AI产品经理"],  # append
                "locations": ["广州"],  # append
            }
        }
        merged = await service.merge_session_updates(current, updates)

        assert "产品经理" in merged.preferences.target_roles
        assert "AI产品经理" in merged.preferences.target_roles
        assert "深圳" in merged.preferences.locations
        assert "广州" in merged.preferences.locations

    @pytest.mark.asyncio
    async def test_user_merge_list_append(self, mock_db, tmp_dir):
        """UserMemory list 字段 append 去重"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = UserMemory(negative_signals=["不做销售"])
        updates = {"negative_signals": ["不做销售", "不去北京"]}
        merged = await service.merge_user_updates(current, updates)

        assert merged.negative_signals == ["不做销售", "不去北京"]

    @pytest.mark.asyncio
    async def test_user_merge_scalar_overwrite(self, mock_db, tmp_dir):
        """UserMemory 标量字段覆盖"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = UserMemory(career_direction="旧方向")
        updates = {"career_direction": "新方向"}
        merged = await service.merge_user_updates(current, updates)

        assert merged.career_direction == "新方向"


# ── Scenario D: Render/Parse roundtrip ───────────────────────────────────


class TestRenderParseRoundtrip:
    """验证 markdown render → parse 不丢字段"""

    def test_session_roundtrip(self, sample_session_memory):
        """SessionMemory render → parse 往返"""
        rendered = render_session_memory(sample_session_memory)
        parsed = parse_session_memory(rendered)

        assert parsed is not None
        assert parsed.current_goal == sample_session_memory.current_goal
        assert parsed.preferences.target_roles == sample_session_memory.preferences.target_roles
        assert parsed.preferences.locations == sample_session_memory.preferences.locations
        assert parsed.next_action == sample_session_memory.next_action

    def test_user_memory_render_covers_all_fields(self, sample_user_memory):
        """L2 单向渲染：关键字段均要出现在 /memory/profile.md 里"""
        rendered = render_user_memory(sample_user_memory)

        assert sample_user_memory.career_direction in rendered
        assert "不做销售" in rendered
        assert "target_roles: 产品经理" in rendered
        assert "locations: user" in rendered
        assert "target_roles: resume" in rendered


# ── Scenario E: L2 写入来源仲裁（Phase 3.3）──────────────────────────────


class TestPreferenceArbitration:
    """user > agent > resume；resume 只填空"""

    @pytest.mark.asyncio
    async def test_resume_does_not_override_user_field(self, mock_db, tmp_dir):
        """简历重解析不得抹掉用户在设置页确认的偏好"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = UserMemory(
            long_term_preferences=JobPreference(locations=["上海"]),
            preference_sources={"locations": "user"},
        )
        merged = await service.merge_with_source(
            current, {"long_term_preferences": {"locations": ["北京"]}}, source="resume"
        )

        assert merged.long_term_preferences.locations == ["上海"]
        assert merged.preference_sources["locations"] == "user"

    @pytest.mark.asyncio
    async def test_resume_does_not_extend_confirmed_list(self, mock_db, tmp_dir):
        """resume 也不通过 append 扩写已有清单（避免简历里的技能淹没用户意图）"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = UserMemory(
            long_term_preferences=JobPreference(target_roles=["产品经理"]),
            preference_sources={"target_roles": "agent"},
        )
        merged = await service.merge_with_source(
            current,
            {"long_term_preferences": {"target_roles": ["产品专员"]}},
            source="resume",
        )

        assert merged.long_term_preferences.target_roles == ["产品经理"]

    @pytest.mark.asyncio
    async def test_resume_fills_empty_field(self, mock_db, tmp_dir):
        """字段为空时 resume 能填上，并记为 resume 所有"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = UserMemory(long_term_preferences=JobPreference(industries=[]))
        merged = await service.merge_with_source(
            current,
            {"long_term_preferences": {"industries": ["互联网"]}},
            source="resume",
        )

        assert merged.long_term_preferences.industries == ["互联网"]
        assert merged.preference_sources["industries"] == "resume"

    @pytest.mark.asyncio
    async def test_agent_does_not_override_user(self, mock_db, tmp_dir):
        """agent 对话抽取不覆盖用户显式确认的值"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = UserMemory(
            career_direction="消费产品",
            preference_sources={"career_direction": "user"},
        )
        merged = await service.merge_with_source(
            current, {"career_direction": "推荐算法"}, source="agent"
        )

        assert merged.career_direction == "消费产品"

    @pytest.mark.asyncio
    async def test_user_overrides_agent(self, mock_db, tmp_dir):
        """高优先级写入覆盖低优先级来源，并改写归属"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = UserMemory(
            long_term_preferences=JobPreference(locations=["深圳"]),
            preference_sources={"locations": "agent"},
        )
        merged = await service.merge_with_source(
            current, {"long_term_preferences": {"locations": ["杭州"]}}, source="user"
        )

        assert merged.long_term_preferences.locations == ["杭州"]
        assert merged.preference_sources["locations"] == "user"

    @pytest.mark.asyncio
    async def test_agent_appends_own_list(self, mock_db, tmp_dir):
        """同优先级（agent 写 agent 所有）依旧 append 去重"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = UserMemory(
            long_term_preferences=JobPreference(skills=["Python"]),
            preference_sources={"skills": "agent"},
        )
        merged = await service.merge_with_source(
            current,
            {"long_term_preferences": {"skills": ["Python", "SQL"]}},
            source="agent",
        )

        assert merged.long_term_preferences.skills == ["Python", "SQL"]

    @pytest.mark.asyncio
    async def test_merge_does_not_mutate_input(self, mock_db, tmp_dir):
        """仲裁返回新对象，不就地修改入参（调用方可能还要用原值）"""
        service = MemoryService(mock_db, base_dir=tmp_dir)
        current = UserMemory(long_term_preferences=JobPreference(locations=["深圳"]))
        await service.merge_with_source(
            current, {"long_term_preferences": {"locations": ["广州"]}}, source="agent"
        )

        assert current.long_term_preferences.locations == ["深圳"]
        assert current.preference_sources == {}
