"""Unit tests for markdown renderer — 渲染往返不丢字段。"""
import pytest
from datetime import datetime

from app.memory.schemas import (
    UserMemory, SessionMemory, JobPreference, SalaryRange,
)
from app.memory.markdown_renderer import (
    render_user_memory,
    render_session_memory,
    parse_session_memory,
)


# ── UserMemory render（L2 单向投影，无 parse 回路）─────────────────────────

class TestUserMemoryRenderer:
    def test_render_empty(self):
        mem = UserMemory()
        md = render_user_memory(mem)
        assert "# 用户长期画像" in md
        assert "## Metadata" in md
        assert "## 长期偏好" in md
        # 稳定事实章节已随 agent-context-overhaul Phase 3 退役
        assert "稳定事实" not in md

    def test_render_full(self):
        mem = UserMemory(
            long_term_preferences=JobPreference(
                target_roles=["产品经理"],
                locations=["深圳"],
                salary=SalaryRange(min=15000, max=25000),
                target_companies=["字节"],
                target_company_types=["大厂"],
                industries=["AI"],
                recruitment_types=["GRADUATE"],
                skills=["Python", "React"],
            ),
            preference_sources={"locations": "user"},
            negative_signals=["不做销售"],
            career_direction="AI产品方向",
            last_updated=datetime(2026, 8, 15, 14, 30),
        )
        md = render_user_memory(mem)
        assert "target_roles: 产品经理" in md
        assert "locations: 深圳" in md
        assert "min: 15000" in md
        assert "max: 25000" in md
        assert "target_companies: 字节" in md
        assert "target_company_types: 大厂" in md
        assert "不做销售" in md
        assert "AI产品方向" in md
        # 偏好来源可见，agent 才能区分“简历推的”与“用户自己说的”
        assert "locations: user" in md

    def test_l2_has_no_parse_counterpart(self):
        """L2 只读：防止有人又把 markdown → DB 的回写回路加回来。"""
        import app.memory.markdown_renderer as mr

        assert not hasattr(mr, "parse_user_memory")


# ── SessionMemory render/parse roundtrip ──────────────────────────────────

class TestSessionMemoryRenderer:
    def test_render_empty(self):
        mem = SessionMemory()
        md = render_session_memory(mem)
        assert "# 对话状态" in md
        assert "## 目标 (current_goal)" in md
        assert "auto" in md

    def test_render_full(self):
        mem = SessionMemory(
            current_goal="字节产品岗",
            preferences=JobPreference(
                target_roles=["产品经理"],
                locations=["深圳"],
            ),
            preference_sources={"target_roles": "user_confirmed"},
            open_questions=["是否接受实习？"],
            recent_decisions=["选择深圳"],
            next_action="搜索岗位",
            last_updated=datetime(2026, 8, 15, 15, 0),
        )
        md = render_session_memory(mem)
        assert "字节产品岗" in md
        assert "target_roles: 产品经理" in md
        assert "target_roles: user_confirmed" in md
        assert "是否接受实习？" in md
        assert "选择深圳" in md
        assert "搜索岗位" in md

    def test_roundtrip_preserves_data(self):
        original = SessionMemory(
            current_goal="字节产品岗",
            preferences=JobPreference(
                target_roles=["产品经理"],
                locations=["深圳", "广州"],
            ),
            preference_sources={"locations": "user_stated"},
            open_questions=["实习？"],
            recent_decisions=["选深圳"],
            next_action="搜索",
            last_updated=datetime(2026, 8, 15, 15, 0),
        )
        md = render_session_memory(original)
        parsed = parse_session_memory(md)
        assert parsed is not None
        assert parsed.current_goal == "字节产品岗"
        assert parsed.preferences.target_roles == ["产品经理"]
        assert parsed.preferences.locations == ["深圳", "广州"]
        assert parsed.preference_sources.get("locations") == "user_stated"
        assert parsed.open_questions == ["实习？"]
        assert parsed.recent_decisions == ["选深圳"]
        assert parsed.next_action == "搜索"

    def test_parse_empty_returns_defaults(self):
        md = render_session_memory(SessionMemory())
        parsed = parse_session_memory(md)
        assert parsed is not None
        assert parsed.current_goal == "auto"
        assert parsed.preferences.target_roles == []
        assert parsed.open_questions == []
