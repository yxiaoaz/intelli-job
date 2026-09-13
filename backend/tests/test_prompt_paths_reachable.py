"""agent-context-overhaul Phase 4/5 验收：prompt 声明的文件路径必须真的可达。

判定口径（tasks.md 5.2）：**不返回 error 即算命中**——`/resume/active.md` 无数据时
返回占位文本属预期通过态。因此另配一个 negative control，避免整组断言永远绿灯。

这条测试不经过 LLM：旧版 `user-{id}/` 前缀在 virtual_mode 下会被解成
`user-{id}/user-{id}/…` 而静默 not found，靠 agent `ls` 自愈掩盖掉了。
把"prompt 写的路径 == 运行期可读的路径"固化成永久回归，成本极低。
"""
import re
import uuid
from types import SimpleNamespace

import pytest

import app.core.agents.conversation_agent as ca_module
from app.core.backends.db_backend import NO_RESUME_TEXT
from app.memory.schemas import JobPreference, UserMemory
from app.memory.service import MemoryService

USER_ID = str(uuid.uuid4())
SESSION_ID = "11111111-2222-3333-4444-555555555555"

# 只认反引号里以 / 开头、以 .md 结尾的虚拟绝对路径
PATH_IN_BACKTICKS = re.compile(r"`(/[^\s`]+\.md)`")


class _FakeResume:
    def __init__(self, extracted_content=None):
        self.id = uuid.uuid4()
        self.extracted_content = extracted_content
        self.updated_at = None
        self.parsed_at = None


class _FakeResult:
    def __init__(self, item):
        self._item = item

    def scalars(self):
        return SimpleNamespace(first=lambda: self._item)

    def scalar_one_or_none(self):
        return self._item


def _assemble(tmp_path, monkeypatch, resume):
    """跑真实的 _create_agent 装配，抓出 system_prompt 与 backend"""
    captured = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return "fake-agent"

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def execute(self, _stmt):
            return _FakeResult(resume)

    async def fake_get_user_memory(self, user_id):
        return UserMemory(
            long_term_preferences=JobPreference(locations=["杭州"], target_roles=["算法工程师"]),
            preference_sources={"locations": "user"},
            career_direction="往推荐算法方向发展",
        )

    monkeypatch.setattr(ca_module, "create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr(ca_module, "AsyncSessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(MemoryService, "get_user_memory", fake_get_user_memory)

    agent = ca_module.ConversationAgent.__new__(ca_module.ConversationAgent)
    agent.intent_file_service = SimpleNamespace(base_dir=tmp_path)
    agent.llm_service = SimpleNamespace(chat_model=object())
    agent.job_matching_service = SimpleNamespace()

    # L1 会话文件：冷启动规则要求 agent 能读到它，先造出来（等价于跑过一轮）
    user_dir = tmp_path / f"user-{USER_ID}"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / f"session-{SESSION_ID}.md").write_text(
        "# 对话状态\n\n## 目标 (current_goal)\n找杭州算法岗\n", encoding="utf-8"
    )

    agent._create_agent(session_id=SESSION_ID, user_id=USER_ID, checkpointer=None)
    return captured["system_prompt"], captured["backend"]


class TestPromptPathsReachable:
    @pytest.mark.asyncio
    async def test_all_paths_readable_when_resume_active(self, tmp_path, monkeypatch):
        prompt, backend = _assemble(
            tmp_path,
            monkeypatch,
            _FakeResume({"personal_info": {"name": "张三"}, "skills": ["Python"]}),
        )
        paths = set(PATH_IN_BACKTICKS.findall(prompt))
        # 三个核心虚拟路径必须真的被抽到（否则遍历会变成空转）
        assert {
            "/memory/profile.md",
            "/resume/active.md",
            f"/session-{SESSION_ID}.md",
        } <= paths, f"prompt 未声明预期路径，实际抽到：{paths}"

        for path in paths:
            result = await backend.aread(path)
            assert result.error is None, f"prompt 声明的 {path} 实际不可读：{result.error}"

        # 有简历时不能只"不报错"，内容必须真的来自 DB
        resume_content = (await backend.aread("/resume/active.md")).file_data["content"]
        assert "张三" in resume_content
        assert resume_content != NO_RESUME_TEXT

    @pytest.mark.asyncio
    async def test_all_paths_ok_with_placeholder_when_no_resume(self, tmp_path, monkeypatch):
        """无简历是线上常见态：占位文本属通过，但不得是 error"""
        prompt, backend = _assemble(tmp_path, monkeypatch, resume=None)
        paths = set(PATH_IN_BACKTICKS.findall(prompt))

        for path in paths:
            result = await backend.aread(path)
            assert result.error is None, f"{path} 在无简历态下返回了 error：{result.error}"

        assert (
            await backend.aread("/resume/active.md")
        ).file_data["content"] == NO_RESUME_TEXT

    @pytest.mark.asyncio
    async def test_negative_control_unknown_path_still_errors(self, tmp_path, monkeypatch):
        """反证：避免整组断言变成“永远绿灯”"""
        _, backend = _assemble(tmp_path, monkeypatch, resume=None)

        assert (await backend.aread("/nope.md")).error is not None
        assert (await backend.aread("/memory/nope.md")).error is not None

    @pytest.mark.asyncio
    async def test_profile_content_comes_from_l2(self, tmp_path, monkeypatch):
        _, backend = _assemble(tmp_path, monkeypatch, resume=None)
        content = (await backend.aread("/memory/profile.md")).file_data["content"]

        assert "杭州" in content
        assert "往推荐算法方向发展" in content
        # 偏好来源要可见，agent 才分得清"用户说的"与"简历推的"
        assert "locations: user" in content


class TestPromptContentContract:
    """prompt 内容契约：该留的留住，该清的清掉"""

    def test_week_regression_sections_preserved(self, tmp_path, monkeypatch):
        """【面向用户的表达规范】【会话上下文规则】是本周回归验证有效的修复"""
        prompt, _ = _assemble(tmp_path, monkeypatch, resume=None)

        assert "【面向用户的表达规范】" in prompt
        assert "【会话上下文规则】" in prompt
        assert "已为你正在读取" in prompt  # 病句反例说明仍在
        assert "刚才我们在聊X，现在想切到Y对吗？" in prompt

    def test_d11_and_d13_guidance_present(self, tmp_path, monkeypatch):
        prompt, _ = _assemble(tmp_path, monkeypatch, resume=None)

        # D11：偏好改按需读取后，必须有"搜索前先读"引导
        assert "搜索前先读" in prompt or "搜索前先" in prompt
        assert "/memory/profile.md" in prompt
        # D13：冷启动兜底必须指向 L1 会话文件
        assert "冷启动兜底" in prompt
        assert f"/session-{SESSION_ID}.md" in prompt

    def test_host_path_prefix_removed(self, tmp_path, monkeypatch):
        """D14：prompt 里不得再出现 user-{id} 前缀（virtual_mode 下必然 not found）"""
        prompt, _ = _assemble(tmp_path, monkeypatch, resume=None)

        assert "user-{" not in prompt
        assert not re.search(r"user-[0-9a-f]", prompt), "prompt 残留宿主目录前缀"
        assert USER_ID not in prompt

    def test_retired_prompt_wording_gone(self, tmp_path, monkeypatch):
        prompt, _ = _assemble(tmp_path, monkeypatch, resume=None)

        # Phase 3.2：stable_facts 已退役；Phase 4.2：格式示例与"不要修改 profile.md"删除
        assert "stable_facts" not in prompt
        assert "```markdown" not in prompt
        assert "不要修改 profile.md" not in prompt
        # 只读属性改为点名工具
        assert "update_user_memory" in prompt
