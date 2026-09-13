"""agent-context-overhaul Phase 5.1 回归测试：prompt cache 命中可观测。

关键实测结论（决定了这里的取值口径）：
- 流式路径 `response_metadata["token_usage"]` 是 **None**，只有归一化后的
  `usage_metadata["input_token_details"]["cache_read"]`
- 非流式路径才有 provider 原字段 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`
- 不传 `stream_usage=True` 时，流式响应连 usage_metadata 都没有
"""
from types import SimpleNamespace

import pytest

import app.core.agents.conversation_agent as ca_module
from app.services.llm_service import LLMService, extract_prompt_cache_usage


def _msg(usage_metadata=None, token_usage=None):
    return SimpleNamespace(
        usage_metadata=usage_metadata,
        response_metadata={"token_usage": token_usage} if token_usage is not None else {},
    )


class TestExtractPromptCacheUsage:
    def test_streaming_shape_falls_back_to_cache_read(self):
        """流式：token_usage 为 None，miss 用 input - cache_read 推算"""
        msg = _msg(usage_metadata={
            "input_tokens": 788,
            "output_tokens": 10,
            "total_tokens": 798,
            "input_token_details": {"cache_read": 640},
            "output_token_details": {},
        })
        assert extract_prompt_cache_usage(msg) == {
            "hit": 640,
            "miss": 148,
            "input_tokens": 788,
        }

    def test_non_streaming_shape_prefers_provider_fields(self):
        msg = _msg(
            usage_metadata={"input_tokens": 788, "input_token_details": {"cache_read": 640}},
            token_usage={
                "prompt_tokens": 788,
                "prompt_cache_hit_tokens": 640,
                "prompt_cache_miss_tokens": 148,
            },
        )
        assert extract_prompt_cache_usage(msg) == {
            "hit": 640,
            "miss": 148,
            "input_tokens": 788,
        }

    def test_zero_hit_is_not_treated_as_missing(self):
        """首轮全 miss 时 hit=0 是有效数据，不能因为 falsy 就回落/返回 None"""
        msg = _msg(usage_metadata={"input_tokens": 788, "input_token_details": {"cache_read": 0}})
        assert extract_prompt_cache_usage(msg) == {"hit": 0, "miss": 788, "input_tokens": 788}

    def test_openai_style_cached_tokens(self):
        msg = _msg(
            usage_metadata={"input_tokens": 500},
            token_usage={"prompt_tokens": 500, "prompt_tokens_details": {"cached_tokens": 256}},
        )
        assert extract_prompt_cache_usage(msg)["hit"] == 256

    def test_returns_none_when_provider_reports_nothing(self):
        """取不到就返回 None：缺失本身就是信息，不臆造成 0"""
        assert extract_prompt_cache_usage(_msg()) is None
        assert extract_prompt_cache_usage(None) is None
        assert extract_prompt_cache_usage(
            _msg(usage_metadata={"input_tokens": 10, "output_tokens": 5})
        ) is None


class TestStreamUsageConfigured:
    def test_chat_providers_enable_stream_usage(self):
        """没开 stream_usage 就没有任何 usage 可观测，Phase 5.1 会静默失效"""
        service = LLMService()
        for _, model in service._providers:
            assert getattr(model, "stream_usage", False) is True


class TestCacheUsageLoggedPerTurn:
    @staticmethod
    async def _collect(monkeypatch, events):
        recorder = []
        monkeypatch.setattr(
            ca_module,
            "_log_prompt_cache_usage",
            lambda session_id, usages: recorder.append((session_id, usages)),
        )

        class _FakeAgent:
            async def astream_events(self, messages, config=None, version="v2"):
                for ev in events:
                    yield ev

        agent = ca_module.ConversationAgent.__new__(ca_module.ConversationAgent)
        agent._stream_source_name = "FallbackChatModel"

        async def fake_prepare(message, session_id, user_id=None):
            return _FakeAgent(), {"configurable": {"thread_id": session_id}}, []

        monkeypatch.setattr(agent, "_prepare_messages", fake_prepare)

        async for _ in agent.chat_stream(message="hi", session_id="s-1"):
            pass
        return recorder

    @pytest.mark.asyncio
    async def test_logs_outer_model_calls_only(self, monkeypatch):
        events = [
            {
                "event": "on_chat_model_end",
                "name": "FallbackChatModel",
                "data": {"output": _msg(usage_metadata={
                    "input_tokens": 800,
                    "input_token_details": {"cache_read": 640},
                })},
            },
            {
                # 内层 / 内部 LLM 调用（名字不是外层来源）不得计入
                "event": "on_chat_model_end",
                "name": "ChatOpenAI",
                "data": {"output": _msg(usage_metadata={
                    "input_tokens": 9999,
                    "input_token_details": {"cache_read": 9999},
                })},
            },
            {
                "event": "on_chat_model_end",
                "name": "FallbackChatModel",
                "data": {"output": _msg(usage_metadata={
                    "input_tokens": 900,
                    "input_token_details": {"cache_read": 832},
                })},
            },
        ]
        recorder = await self._collect(monkeypatch, events)

        assert len(recorder) == 1, "每轮只输出一条汇总日志"
        session_id, usages = recorder[0]
        assert session_id == "s-1"
        assert [u["hit"] for u in usages] == [640, 832]
        assert [u["miss"] for u in usages] == [160, 68]

    @pytest.mark.asyncio
    async def test_still_logs_when_usage_missing(self, monkeypatch):
        """没有任何 usage 也要出日志行，否则分不清“没数据”与“没埋点”"""
        events = [
            {
                "event": "on_chat_model_end",
                "name": "FallbackChatModel",
                "data": {"output": _msg()},
            }
        ]
        recorder = await self._collect(monkeypatch, events)

        assert recorder == [("s-1", [])]
