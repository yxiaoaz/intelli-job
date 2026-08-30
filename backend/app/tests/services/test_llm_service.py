"""LLMService 多供应商 fallback 与智能重试单元测试。

覆盖：
- 主供应商抛可重试异常（重试耗尽）→ fallback 供应商被调用、返回成功
- 主供应商抛 4xx 永久性错误 → 不重试、直接切 fallback
- 所有供应商失败 → 抛最后异常
- 无 fallback 配置时行为与旧版一致（单供应商 + 重试）
- chat_model 在多供应商时是 FallbackChatModel（deepagents 兼容的 fallback 链，
  不能用 with_fallbacks：RunnableWithFallbacks 非 BaseChatModel 子类，
  deepagents resolve_model 会把它误当字符串 spec 解析而崩溃）
- 异常分类：RETRYABLE_EXCEPTIONS 每类触发重试；AuthenticationError/BadRequestError 不重试
"""

import httpx
import pytest
from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

from app.services.llm_service import FallbackChatModel, LLMService, RETRYABLE_EXCEPTIONS


# ── 测试工具 ──────────────────────────────────────────────────────────────

class FakeModel:
    """最小 ChatModel 替身：记录调用次数，按预设抛异常或返回内容"""

    def __init__(self, name: str, exc: Exception | None = None, content: str = "ok"):
        self.model_name = name
        self.calls = 0
        self._exc = exc
        self._content = content

    async def ainvoke(self, messages, **kwargs):
        self.calls += 1
        if self._exc is not None:
            raise self._exc

        class _Resp:
            content = self._content

        return _Resp()

    def with_fallbacks(self, fallbacks):
        # Runnable 接口替身：fallback 测试不依赖真实包装器
        return self


def _openai_error(cls, status_code: int | None = None) -> Exception:
    """构造带合法 httpx response/request 的 openai 异常"""
    request = httpx.Request("POST", "https://api.test/v1/chat/completions")
    if cls is APITimeoutError:
        return cls(request)
    if cls is APIConnectionError:
        return cls(message="connection error", request=request)
    response = httpx.Response(status_code=status_code, request=request)
    return cls("error", response=response, body=None)


@pytest.fixture(autouse=True)
def _no_tenacity_wait(monkeypatch):
    """跳过 tenacity 退避等待，加速重试测试"""
    import tenacity.nap

    monkeypatch.setattr(tenacity.nap, "sleep", lambda seconds: None)


def _make_service(*models: FakeModel) -> LLMService:
    return LLMService(providers=[(m.model_name, m) for m in models])


MESSAGES = [{"role": "user", "content": "hello"}]


# ── fallback 行为 ─────────────────────────────────────────────────────────

class TestFallback:

    @pytest.mark.asyncio
    async def test_retryable_exhausted_falls_back(self):
        """主供应商 RateLimitError 重试耗尽 → fallback 被调用并返回成功"""
        main = FakeModel("main", exc=_openai_error(RateLimitError, 429))
        backup = FakeModel("backup", content="from-backup")
        service = _make_service(main, backup)

        result = await service.generate_completion(MESSAGES)

        assert result == "from-backup"
        assert main.calls == 2   # stop_after_attempt(2)
        assert backup.calls == 1

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry_falls_back(self):
        """主供应商 4xx 永久性错误 → 不重试，直接切 fallback"""
        main = FakeModel("main", exc=_openai_error(AuthenticationError, 401))
        backup = FakeModel("backup", content="from-backup")
        service = _make_service(main, backup)

        result = await service.generate_completion(MESSAGES)

        assert result == "from-backup"
        assert main.calls == 1   # 4xx 不重试
        assert backup.calls == 1

    @pytest.mark.asyncio
    async def test_all_providers_failed_raises_last_error(self):
        """所有供应商失败 → 抛出最后一个异常"""
        first = FakeModel("first", exc=_openai_error(RateLimitError, 429))
        second = FakeModel("second", exc=_openai_error(AuthenticationError, 401))
        service = _make_service(first, second)

        with pytest.raises(AuthenticationError):
            await service.generate_completion(MESSAGES)

        assert first.calls == 2
        assert second.calls == 1

    @pytest.mark.asyncio
    async def test_three_providers_chain(self):
        """三家供应商链：前两家失败，第三家救场"""
        m1 = FakeModel("p1", exc=_openai_error(APITimeoutError))
        m2 = FakeModel("p2", exc=_openai_error(BadRequestError, 400))
        m3 = FakeModel("p3", content="from-p3")
        service = _make_service(m1, m2, m3)

        result = await service.generate_completion(MESSAGES)

        assert result == "from-p3"
        assert m1.calls == 2
        assert m2.calls == 1
        assert m3.calls == 1


# ── 单供应商（无 fallback，等价旧版行为）───────────────────────────────────

class TestSingleProvider:

    @pytest.mark.asyncio
    async def test_success(self):
        model = FakeModel("only", content="ok")
        service = _make_service(model)

        assert await service.generate_completion(MESSAGES) == "ok"
        assert model.calls == 1

    @pytest.mark.asyncio
    async def test_retryable_still_retried_without_fallback(self):
        """单供应商可重试异常 → 仍重试 2 次后抛出"""
        model = FakeModel("only", exc=_openai_error(RateLimitError, 429))
        service = _make_service(model)

        with pytest.raises(RateLimitError):
            await service.generate_completion(MESSAGES)

        assert model.calls == 2


# ── chat_model with_fallbacks ─────────────────────────────────────────────

class TestChatModel:

    def test_chat_model_with_fallbacks(self):
        """多供应商时 chat_model 为 FallbackChatModel（deepagents 兼容）"""
        service = LLMService(
            providers=[
                ("main", ChatOpenAI(model="m1", api_key="test")),
                ("backup", ChatOpenAI(model="m2", api_key="test")),
            ]
        )
        assert isinstance(service.chat_model, FallbackChatModel)
        assert len(service.chat_model.models) == 2

    def test_chat_model_plain_without_fallback(self):
        """单供应商时 chat_model 为主模型本身（与旧版一致）"""
        model = ChatOpenAI(model="m1", api_key="test")
        service = LLMService(providers=[("main", model)])
        assert service.chat_model is model


# ── 异常分类 ──────────────────────────────────────────────────────────────

class TestExceptionClassification:

    @pytest.mark.parametrize("exc_cls,status", [
        (RateLimitError, 429),
        (APITimeoutError, None),
        (APIConnectionError, None),
        (InternalServerError, 500),
    ])
    @pytest.mark.asyncio
    async def test_retryable_exceptions_trigger_retry(self, exc_cls, status):
        """RETRYABLE_EXCEPTIONS 每类异常均触发重试（单供应商重试 2 次）"""
        model = FakeModel("only", exc=_openai_error(exc_cls, status) if status else _openai_error(exc_cls))
        service = _make_service(model)

        with pytest.raises(exc_cls):
            await service.generate_completion(MESSAGES)

        assert model.calls == 2

    @pytest.mark.parametrize("exc_cls,status", [
        (AuthenticationError, 401),
        (BadRequestError, 400),
    ])
    @pytest.mark.asyncio
    async def test_permanent_exceptions_no_retry(self, exc_cls, status):
        """永久性 4xx 异常不触发重试（单供应商只调 1 次即抛出）"""
        model = FakeModel("only", exc=_openai_error(exc_cls, status))
        service = _make_service(model)

        with pytest.raises(exc_cls):
            await service.generate_completion(MESSAGES)

        assert model.calls == 1

    def test_retryable_tuple_contents(self):
        """RETRYABLE_EXCEPTIONS 覆盖限流/超时/连接/5xx 四类"""
        assert RETRYABLE_EXCEPTIONS == (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            InternalServerError,
        )


# ── FallbackChatModel（Agent 链路的 BaseChatModel 接口 fallback）──────────

class _FakeStreamModel:
    """流式替身：可预设异常，产出两个 token"""

    def __init__(self, name: str, exc: Exception | None = None):
        self.model_name = name
        self._exc = exc

    def bind_tools(self, tools, **kwargs):
        return self

    async def astream(self, messages, **kwargs):
        from langchain_core.messages import AIMessageChunk

        if self._exc is not None:
            raise self._exc
        for token in ["你好", "！"]:
            yield AIMessageChunk(content=token)


class TestFallbackChatModel:

    @pytest.mark.asyncio
    async def test_astream_falls_back_when_first_provider_fails(self):
        """首供应商在产出任何 token 前失败 → 切下一供应商，输出完整"""
        from langchain_core.messages import HumanMessage

        primary = _FakeStreamModel(
            "m1", exc=APITimeoutError(httpx.Request("POST", "https://api.test"))
        )
        backup = _FakeStreamModel("m2")
        chain = FallbackChatModel(models=[primary, backup])

        chunks = [c async for c in chain.astream([HumanMessage(content="hi")])]
        # BaseChatModel.astream yield 的是 AIMessageChunk
        assert "".join(c.content for c in chunks) == "你好！"

    @pytest.mark.asyncio
    async def test_astream_raises_when_all_fail(self):
        from langchain_core.messages import HumanMessage

        exc = APITimeoutError(httpx.Request("POST", "https://api.test"))
        chain = FallbackChatModel(
            models=[_FakeStreamModel("m1", exc=exc), _FakeStreamModel("m2", exc=exc)]
        )
        with pytest.raises(APITimeoutError):
            async for _ in chain.astream([HumanMessage(content="hi")]):
                pass

    def test_bind_tools_keeps_fallback_chain(self):
        """bind_tools 后仍是 FallbackChatModel 且供应商数不变"""
        chain = FallbackChatModel(
            models=[
                ChatOpenAI(model="m1", api_key="test"),
                ChatOpenAI(model="m2", api_key="test"),
            ]
        )
        bound = chain.bind_tools([{"type": "function", "function": {"name": "f"}}])
        assert isinstance(bound, FallbackChatModel)
        assert len(bound.models) == 2
