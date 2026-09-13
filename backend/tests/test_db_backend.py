"""agent-context-overhaul Phase 2 回归测试：DbBackend 虚拟文件 + CompositeBackend 路由。

不依赖真实数据库：用桩 session 与 monkeypatch 覆盖三类行为——
按需渲染、只读拒绝写入、异常不外抛。
"""
import uuid

import pytest
from deepagents.backends import CompositeBackend, FilesystemBackend
from app.memory.schemas import UserMemory  # noqa: F401  （预留：后续用例构造完整 L2）
from app.memory.service import MemoryService

from app.core.backends.db_backend import (
    DB_ERROR_TEXT,
    NO_PARSED_TEXT,
    NO_RESUME_TEXT,
    READONLY_ERROR,
    DbBackend,
    _canonical,
)
from app.core.backends.renderers import render_resume_markdown

USER_ID = str(uuid.uuid4())


class _FakeScalars:
    def __init__(self, item):
        self._item = item

    def first(self):
        return self._item


class _FakeResult:
    def __init__(self, item):
        self._item = item

    def scalars(self):
        return _FakeScalars(self._item)


class _FakeResume:
    def __init__(self, extracted_content):
        self.id = uuid.uuid4()
        self.extracted_content = extracted_content
        self.updated_at = None
        self.parsed_at = None


class _FakeSession:
    """模拟 async session：可配置返回某份简历，或直接抛异常"""

    def __init__(self, resume=None, raise_exc=False):
        self._resume = resume
        self._raise = raise_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, _stmt):
        if self._raise:
            raise RuntimeError("db down")
        return _FakeResult(self._resume)


def _backend(resume=None, raise_exc=False):
    return DbBackend(
        user_id=USER_ID,
        session_factory=lambda: _FakeSession(resume=resume, raise_exc=raise_exc),
        base_dir="workspace-test",
    )


class TestPathCanonical:
    """CompositeBackend 会剥掉路由前缀，两种形态都要能命中同一数据源"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("/resume/active.md", "/active.md"),
            ("/active.md", "/active.md"),
            ("/memory/profile.md", "/profile.md"),
            ("/profile.md", "/profile.md"),
            ("active.md", "/active.md"),
            ("/", "/"),
        ],
    )
    def test_canonical(self, raw, expected):
        assert _canonical(raw) == expected


class TestRead:
    @pytest.mark.asyncio
    async def test_active_resume_rendered_from_extracted_content(self):
        resume = _FakeResume(
            {
                "personal_info": {"name": "张三", "location": "杭州"},
                "education": [{"school": "浙大", "degree": "硕士", "major": "计算机"}],
                "work_experience": [{"company": "阿里", "title": "数据分析师"}],
                "skills": ["SQL", "Python"],
            }
        )
        result = await _backend(resume=resume).aread("/resume/active.md")
        assert result.error is None
        content = result.file_data["content"]
        assert "张三" in content and "浙大" in content and "SQL" in content
        # 兼容旧数据的 title 字段
        assert "阿里" in content and "数据分析师" in content

    @pytest.mark.asyncio
    async def test_no_active_resume_returns_placeholder_not_error(self):
        """无简历必须给占位文本：报"文件不存在"会让 agent 陷入重试循环"""
        result = await _backend(resume=None).aread("/active.md")
        assert result.error is None
        assert result.file_data["content"] == NO_RESUME_TEXT

    @pytest.mark.asyncio
    async def test_uploaded_but_unparsed(self):
        result = await _backend(resume=_FakeResume(None)).aread("/active.md")
        assert result.file_data["content"] == NO_PARSED_TEXT

    @pytest.mark.asyncio
    async def test_db_failure_degrades_to_text_without_raising(self):
        """查询异常不能冒泡中断 agent 循环（design.md「失败与降级」）"""
        result = await _backend(raise_exc=True).aread("/active.md")
        assert result.error is None
        assert result.file_data["content"] == DB_ERROR_TEXT

    @pytest.mark.asyncio
    async def test_unknown_path_lists_available_paths(self):
        result = await _backend().aread("/resume/other.md")
        assert result.error and "/resume/active.md" in result.error

    @pytest.mark.asyncio
    async def test_profile_renders_even_without_record(self, monkeypatch):
        """无 L2 记录也要出空骨架，agent 才知道哪些字段还空着"""

        async def fake_get(self, user_id):
            return None

        monkeypatch.setattr(MemoryService, "get_user_memory", fake_get)
        result = await _backend().aread("/memory/profile.md")
        assert result.error is None
        assert "用户长期画像" in result.file_data["content"]


class TestReadOnly:
    @pytest.mark.asyncio
    async def test_awrite_and_aedit_return_guidance(self):
        backend = _backend()
        write_result = await backend.awrite("/memory/profile.md", "x")
        edit_result = await backend.aedit("/memory/profile.md", "a", "b")
        assert write_result.error == READONLY_ERROR
        assert edit_result.error == READONLY_ERROR
        # 错误文案必须点名替代工具，否则 agent 会反复重试
        assert "update_user_memory" in write_result.error

    def test_sync_write_edit_too(self):
        backend = _backend()
        assert backend.write("/memory/profile.md", "x").error == READONLY_ERROR
        assert backend.edit("/memory/profile.md", "a", "b").error == READONLY_ERROR

    @pytest.mark.asyncio
    async def test_ls_and_glob_expose_virtual_files(self):
        backend = _backend()
        listed = await backend.als("/")
        paths = {e["path"] for e in (listed.entries or [])}
        assert paths == {"/resume/active.md", "/memory/profile.md"}
        # 路由根目录被 CompositeBackend 传成 "/"，此时只列该路由自己的文件
        assert [e["path"] for e in (await backend.als("/resume")).entries] == [
            "/resume/active.md"
        ]
        matched = await backend.aglob("*.md")
        assert len(matched.matches) == 2


class TestUserIsolation:
    @pytest.mark.asyncio
    async def test_user_id_is_bound_at_construction(self):
        """构造时固定 user_id，越权依赖查询条件而非调用方传参"""
        backend = _backend()
        assert str(backend._user_id) == USER_ID


class TestCompositeRouting:
    """D14 复测：带前导 `/` 且不命中任何路由 → 应落到 default 分支"""

    @pytest.mark.asyncio
    async def test_unrouted_path_goes_to_filesystem_default(self, tmp_path):
        fs = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
        composite = CompositeBackend(
            default=fs,
            routes={"/resume/": _backend(), "/memory/": _backend()},
            artifacts_root="/artifacts/",
        )
        (tmp_path / "session-abc.md").write_text("# 会话状态\n目标：算法岗", encoding="utf-8")

        result = await composite.aread("/session-abc.md")
        assert result.error is None
        assert "算法岗" in result.file_data["content"]

    @pytest.mark.asyncio
    async def test_routed_paths_reach_db_backend(self):
        composite = CompositeBackend(
            default=FilesystemBackend(virtual_mode=True, root_dir="."),
            routes={"/resume/": _backend(), "/memory/": _backend()},
        )
        result = await composite.aread("/resume/active.md")
        assert result.file_data["content"] == NO_RESUME_TEXT


class TestResumeRenderer:
    def test_empty_content_gives_hint_not_blank(self):
        assert render_resume_markdown({}).startswith("（")

    def test_skills_as_comma_string(self):
        md = render_resume_markdown({"skills": "Python, SQL ,"})
        assert "Python" in md and "SQL" in md

    def test_non_dict_entries_tolerated(self):
        md = render_resume_markdown({"work_experience": ["不是字典", {"company": "A"}]})
        assert "A" in md
