"""agent-context-overhaul Phase 1 回归测试：checkpointer 基建与压缩阈值。

覆盖：
- psycopg 3 DSN 与 SQLAlchemy 方言串隔离（1.1）
- 开关关闭时 init 不做任何事（1.1）
- 开 / 关两种路径下 _prepare_messages 的消息装配行为（1.2 + 4.1，含回滚分支）
- config 带上 recursion_limit 护栏（4.1）
- 模型暴露 max_input_tokens 使主动压缩可触发（1.3 D12）
"""
import asyncio
import selectors

import pytest

import app.core.agents.conversation_agent as ca_module
from app.config import get_settings
from app.core import checkpointer_factory
from app.core.checkpointer_factory import get_checkpointer, init_checkpointer


def _selector_run(coro):
    """Windows 默认 ProactorEventLoop 无法跑 psycopg async，测试内统一用 selector loop"""
    return asyncio.run(
        coro,
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )


class TestConfigIsolation:
    """1.1 依赖与连接串"""

    def test_checkpointer_dsn_is_not_sqlalchemy_url(self):
        """DATABASE_URL 带 +asyncpg 方言，不能直接喂给 saver；DSN 必须独立构造"""
        settings = get_settings()
        assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
        assert "+asyncpg" not in settings.CHECKPOINTER_DSN
        assert settings.CHECKPOINTER_DSN.startswith("postgresql://")

    def test_init_is_noop_when_flag_disabled(self, monkeypatch):
        """ENABLE_AGENT_CHECKPOINTER=False → 不建池，get_checkpointer() 返回 None（回滚路径）"""
        monkeypatch.setattr(
            checkpointer_factory, "_saver", None
        )
        monkeypatch.setattr(get_settings(), "ENABLE_AGENT_CHECKPOINTER", False, raising=False)
        # Settings 是 lru_cache 单例，直接改实例字段即可被 init 读到
        _selector_run(init_checkpointer())
        assert get_checkpointer() is None


class TestPrepareMessagesBranching:
    """1.2 接入 agent：开 / 关两条路径的消息装配"""

    @staticmethod
    def _make_agent(recorder):
        """跳过 __init__（避免依赖真实 LLM 供应商配置）的 ConversationAgent"""
        agent = ca_module.ConversationAgent.__new__(ca_module.ConversationAgent)

        def fake_create_agent(session_id, user_id=None, checkpointer=None):
            recorder["checkpointer"] = checkpointer
            return "fake-agent"

        agent._create_agent = fake_create_agent
        return agent

    @pytest.mark.asyncio
    async def test_only_current_message_when_checkpointer_on(self, monkeypatch):
        """有 checkpointer：只传本轮用户消息，且不注入动态 system message（D4 雪球防护）"""
        sentinel = object()
        recorder = {}
        monkeypatch.setattr(ca_module, "get_checkpointer", lambda: sentinel)
        monkeypatch.setattr(get_settings(), "ENABLE_AGENT_CHECKPOINTER", True, raising=False)

        agent = self._make_agent(recorder)
        result_agent, config, messages = await agent._prepare_messages(
            message="帮我找算法岗", session_id="s-1", user_id="u-1"
        )

        assert result_agent == "fake-agent"
        assert recorder["checkpointer"] is sentinel
        assert config["configurable"]["thread_id"] == "s-1"
        assert messages == [{"role": "user", "content": "帮我找算法岗"}]

    @pytest.mark.asyncio
    async def test_legacy_history_path_when_flag_off(self, monkeypatch):
        """开关关闭：不读 factory，传 checkpointer=None，保留历史重建但不拼动态 system message"""
        recorder = {}

        def must_not_be_called():
            raise AssertionError("开关关闭时不应读取 checkpointer factory")

        monkeypatch.setattr(ca_module, "get_checkpointer", must_not_be_called)
        monkeypatch.setattr(get_settings(), "ENABLE_AGENT_CHECKPOINTER", False, raising=False)

        def boom(*args, **kwargs):
            raise RuntimeError("no db in unit test")

        monkeypatch.setattr(ca_module, "AsyncSessionLocal", boom)

        agent = self._make_agent(recorder)
        _, _, messages = await agent._prepare_messages(
            message="帮我找算法岗", session_id="s-1", user_id="u-1"
        )

        assert recorder["checkpointer"] is None
        # Phase 4.1：动态 system message 已删除（偏好改读 /memory/profile.md，
        # 路径说明已进 system_prompt），两条分支的 prompt 内容自此单一来源
        assert not any(m["role"] == "system" for m in messages)
        # DB 不可用时当前消息的兜底追加仍要生效
        assert {"role": "user", "content": "帮我找算法岗"} in messages

    @pytest.mark.asyncio
    async def test_recursion_limit_comes_from_settings(self, monkeypatch):
        """config 必须带上 recursion_limit 护栏（Phase 4.1），不能依赖 langgraph 默认 25"""
        sentinel = object()
        recorder = {}
        monkeypatch.setattr(ca_module, "get_checkpointer", lambda: sentinel)
        monkeypatch.setattr(get_settings(), "ENABLE_AGENT_CHECKPOINTER", True, raising=False)
        monkeypatch.setattr(get_settings(), "AGENT_RECURSION_LIMIT", 30, raising=False)

        agent = self._make_agent(recorder)
        _, config, _ = await agent._prepare_messages(
            message="hi", session_id="s-1", user_id="u-1"
        )

        assert config["recursion_limit"] == 30

    @pytest.mark.asyncio
    async def test_legacy_path_when_factory_not_initialized(self, monkeypatch):
        """开关开但 lifespan 未初始化（如未经 lifespan 的测试/脚本）：退回旧路径而不报错"""
        recorder = {}
        monkeypatch.setattr(ca_module, "get_checkpointer", lambda: None)
        monkeypatch.setattr(get_settings(), "ENABLE_AGENT_CHECKPOINTER", True, raising=False)

        def boom(*args, **kwargs):
            raise RuntimeError("no db in unit test")

        monkeypatch.setattr(ca_module, "AsyncSessionLocal", boom)

        agent = self._make_agent(recorder)
        await agent._prepare_messages(
            message="帮我找算法岗", session_id="s-1", user_id="u-1"
        )

        assert recorder["checkpointer"] is None


class TestSummarizationThreshold:
    """1.3 压缩阈值（D12）：必须让主动压缩可触发，而非依赖超限异常兜底"""

    def test_chain_profile_exposes_min_max_input_tokens(self):
        from deepagents.middleware.summarization import compute_summarization_defaults

        from app.services.llm_service import LLMService

        model = LLMService().chat_model
        profile = getattr(model, "profile", None)
        assert isinstance(profile, dict) and profile["max_input_tokens"]

        # 链上各 provider 声明不一致时取最小值（按最弱的一家算）
        declared = [
            int(p["max_input_tokens"])
            for p in get_settings().effective_chat_providers
            if p.get("max_input_tokens")
        ]
        assert profile["max_input_tokens"] == min(declared)

        defaults = compute_summarization_defaults(model)
        assert defaults["trigger"][0] == "fraction", "仍走 170000 tokens 兜底则主动压缩永不触发"
        assert defaults["keep"][0] == "fraction"

    def test_bind_tools_preserves_profile(self):
        """bind_tools 会重新 new 实例，漏传 profile 会让阈值退回默认值"""
        from app.services.llm_service import LLMService

        model = LLMService().chat_model
        assert model.bind_tools([]).profile == model.profile
