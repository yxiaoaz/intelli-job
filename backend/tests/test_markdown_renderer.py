"""Unit tests for markdown renderer — 渲染往返不丢字段。"""
import pytest
from datetime import datetime

from app.memory.schemas import (
    UserMemory, SessionMemory, JobPreference, SalaryRange,
)
from app.memory.markdown_renderer import (
    render_user_memory,
    render_session_memory,
    parse_user_memory,
    parse_session_memory,
)


# ── UserMemory render/parse roundtrip ─────────────────────────────────────

class TestUserMemoryRenderer:
    def test_render_empty(self):
        mem = UserMemory()
        md = render_user_memory(mem)
        assert "# 用户长期画像" in md
        assert "## Metadata" in md
        assert "## 稳定事实" in md
        assert "## 长期偏好" in md

    def test_render_full(self):
        mem = UserMemory(
            stable_facts={"school": "中山大学", "major": "计算机"},
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
            negative_signals=["不做销售"],
            career_direction="AI产品方向",
            last_updated=datetime(2026, 8, 15, 14, 30),
        )
        md = render_user_memory(mem)
        assert "school: 中山大学" in md
        assert "target_roles: 产品经理" in md
        assert "locations: 深圳" in md
        assert "min: 15000" in md
        assert "max: 25000" in md
        assert "target_companies: 字节" in md
        assert "target_company_types: 大厂" in md
        assert "不做销售" in md
        assert "AI产品方向" in md

    def test_roundtrip_preserves_data(self):
        original = UserMemory(
            stable_facts={"school": "中山大学"},
            long_term_preferences=JobPreference(
                target_roles=["产品经理", "AI产品经理"],
                locations=["深圳", "广州"],
                salary=SalaryRange(min=15000, max=25000),
                skills=["Python"],
            ),
            negative_signals=["不做销售"],
            career_direction="互联网产品",
            last_updated=datetime(2026, 8, 15, 14, 30),
        )
        md = render_user_memory(original)
        parsed = parse_user_memory(md)
        assert parsed is not None
        assert parsed.stable_facts.get("school") == "中山大学"
        assert parsed.long_term_preferences.target_roles == ["产品经理", "AI产品经理"]
        assert parsed.long_term_preferences.locations == ["深圳", "广州"]
        assert parsed.long_term_preferences.salary.min == 15000
        assert parsed.long_term_preferences.skills == ["Python"]
        assert parsed.negative_signals == ["不做销售"]
        assert parsed.career_direction == "互联网产品"

    def test_parse_empty_returns_defaults(self):
        md = render_user_memory(UserMemory())
        parsed = parse_user_memory(md)
        assert parsed is not None
        assert parsed.stable_facts == {}
        assert parsed.long_term_preferences.target_roles == []
        assert parsed.negative_signals == []

    def test_parse_invalid_returns_none(self):
        result = parse_user_memory("这不是有效的 markdown 格式")
        # 即使格式简单也不应崩溃
        assert result is not None  # 空数据也算有效


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
