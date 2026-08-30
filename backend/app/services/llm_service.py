import asyncio
from typing import Any, AsyncIterator, Iterator, Optional

from langchain.chat_models.base import BaseChatModel
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.embeddings import Embeddings
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI
from openai import (
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.utils.logger import get_logger
from app.services.aliyun_embeddings import AliyunEmbeddings

settings = get_settings()
logger = get_logger()

# 可重试异常：限流 / 超时 / 连接失败 / 5xx
# 4xx 永久性错误（AuthenticationError / BadRequestError 等）不重试，直接切下一供应商
RETRYABLE_EXCEPTIONS = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


class FallbackChatModel(BaseChatModel):
    """BaseChatModel 接口的多供应商 fallback 链（Agent 流式链路用）。

    为什么不用 model.with_fallbacks()：deepagents 的 resolve_model 用
    isinstance(model, BaseChatModel) 做类型分派，而 RunnableWithFallbacks 只是
    RunnableSerializable，会被误当字符串 spec 解析（apply_provider_profile 里
    spec.count(":") 触发 'ChatOpenAI' object has no attribute 'count'）。
    本类把供应商循环封装成标准 BaseChatModel，deepagents / langgraph 无感知。

    语义：
    - 生成/流式按 provider 顺序尝试，任一异常切下一家，全部失败抛最后一个异常
    - 流式中途（已产出 token 后）失败：不切换（无法无痕续流），向上抛出走 SSE 降级
    - 回调隔离：内部模型调用显式传 config={"callbacks": []}，阻断经 contextvar
      继承外部 tracer，否则每个 token 会双重上报（on_chat_model_stream 双发，
      SSE 输出重复字符）
    """

    # ChatOpenAI 或 bind_tools 后的 RunnableBinding（非 BaseChatModel，故用 Any）
    models: list[Any]

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return False

    @property
    def _llm_type(self) -> str:
        return "fallback-chat-model"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"models": [getattr(m, "model_name", type(m).__name__) for m in self.models]}

    @property
    def model_name(self) -> Optional[str]:
        """deepagents get_model_identifier / 日志兼容"""
        name = getattr(self.models[0], "model_name", None) if self.models else None
        return name if isinstance(name, str) else None

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_exc: Exception | None = None
        for model in self.models:
            try:
                msg = model.invoke(messages, stop=stop, config={"callbacks": []}, **kwargs)
                return ChatResult(generations=[ChatGeneration(message=msg)])
            except Exception as e:
                last_exc = e
                logger.warning(
                    "fallback_chat_model_provider_failed",
                    model=getattr(model, "model_name", type(model).__name__),
                    error=str(e),
                )
        raise last_exc

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_exc: Exception | None = None
        for model in self.models:
            try:
                msg = await model.ainvoke(messages, stop=stop, config={"callbacks": []}, **kwargs)
                return ChatResult(generations=[ChatGeneration(message=msg)])
            except Exception as e:
                last_exc = e
                logger.warning(
                    "fallback_chat_model_provider_failed",
                    model=getattr(model, "model_name", type(model).__name__),
                    error=str(e),
                )
        raise last_exc

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        last_exc: Exception | None = None
        for model in self.models:
            produced = False
            try:
                async for chunk in model.astream(messages, stop=stop, config={"callbacks": []}, **kwargs):
                    produced = True
                    yield ChatGenerationChunk(message=chunk)
                return
            except Exception as e:
                if produced:
                    # 流中途失败：不切换，向上抛出走 SSE 降级帧
                    raise
                last_exc = e
                logger.warning(
                    "fallback_chat_model_provider_failed",
                    model=getattr(model, "model_name", type(model).__name__),
                    error=str(e),
                )
        raise last_exc

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        last_exc: Exception | None = None
        for model in self.models:
            produced = False
            try:
                for chunk in model.stream(messages, stop=stop, config={"callbacks": []}, **kwargs):
                    produced = True
                    yield ChatGenerationChunk(message=chunk)
                return
            except Exception as e:
                if produced:
                    raise
                last_exc = e
                logger.warning(
                    "fallback_chat_model_provider_failed",
                    model=getattr(model, "model_name", type(model).__name__),
                    error=str(e),
                )
        raise last_exc

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FallbackChatModel":
        """deepagents/langgraph 调用点：把绑定后的模型重新装回 fallback 链"""
        return FallbackChatModel(
            models=[m.bind_tools(tools, **kwargs) for m in self.models]
        )


class LLMService:
    """Service for LLM operations using LangChain (model-agnostic)

    Completion 侧维护多供应商链（供应商配置来自 settings.effective_chat_providers）：
    - generate_completion(): 显式循环逐级 fallback，单供应商内部 tenacity 智能重试
    - chat_model: 主模型 with_fallbacks 包装，供 Agent 流式链路使用
    """

    def __init__(self, providers: list[tuple[str, BaseChatModel]] | None = None):
        # 供应商链注入点（测试友好）；默认从配置构建
        if providers is not None:
            self._providers: list[tuple[str, BaseChatModel]] = providers
        else:
            self._providers = [
                (
                    p["name"],
                    ChatOpenAI(
                        model=p["model_name"],
                        temperature=0.7,
                        api_key=p["api_key"],
                        base_url=p["api_url"],
                        timeout=settings.completion_timeout_seconds,
                        max_retries=0,  # 重试收归 tenacity，避免 SDK 与 tenacity 双重重试
                    ),
                )
                for p in settings.effective_chat_providers
            ]

        # Agent 用：多供应商时用 FallbackChatModel（BaseChatModel 接口内的
        # fallback 链，deepagents 兼容）；单供应商直接用裸 ChatOpenAI
        if len(self._providers) > 1:
            self.chat_model: BaseChatModel = FallbackChatModel(
                models=[m for _, m in self._providers]
            )
        else:
            self.chat_model = self._providers[0][1]

        # 使用自定义的 AliyunEmbeddings，直接调用 DashScope API
        # 绕过 LangChain 的 OpenAI 兼容层，避免参数格式问题
        self.embedding_model: Embeddings = AliyunEmbeddings(
            api_key=settings.LLM_EMBEDDING_API_KEY,
            base_url=settings.LLM_EMBEDDING_API_URL,
            model=settings.LLM_EMBEDDING_API_MODEL_NAME,
        )

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def _invoke_provider(self, model: BaseChatModel, messages: list[dict]) -> str:
        """单供应商调用（含智能重试），重试耗尽后向上抛出触发 fallback"""
        response = await model.ainvoke(messages)
        return response.content

    async def generate_completion(self, messages: list[dict]) -> str:
        """Generate completion：逐级遍历供应商链，全部失败才抛出最后一个异常"""
        message_count = len(messages)
        system_msg_preview = ""
        user_msg_preview = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_msg_preview = msg.get("content", "")[:100]
            elif msg.get("role") == "user":
                user_msg_preview = msg.get("content", "")[:100]

        last_error: Exception | None = None
        for idx, (label, model) in enumerate(self._providers):
            next_label = self._providers[idx + 1][0] if idx + 1 < len(self._providers) else None
            try:
                logger.info(
                    "llm_call_start",
                    provider=label,
                    model=model.model_name,
                    message_count=message_count,
                    system_prompt_preview=system_msg_preview,
                    user_prompt_preview=user_msg_preview,
                )

                result_content = await self._invoke_provider(model, messages)

                logger.info(
                    "llm_call_success",
                    provider=label,
                    model=model.model_name,
                    response_length=len(result_content) if isinstance(result_content, str) else 0,
                    response_preview=result_content[:200] if isinstance(result_content, str) else "",
                )
                return result_content
            except RETRYABLE_EXCEPTIONS as e:
                # 重试耗尽仍是可重试类异常 → 切下一供应商
                last_error = e
                logger.warning(
                    "llm_completion_failed",
                    provider=label,
                    model=model.model_name,
                    error=str(e),
                    error_class="retryable",
                )
                self._log_fallback(label, next_label, e, error_class="retryable")
            except Exception as e:
                # 4xx 等永久性错误不重试，直接切下一供应商
                last_error = e
                logger.warning(
                    "llm_completion_failed",
                    provider=label,
                    model=model.model_name,
                    error=str(e),
                    error_class="permanent",
                )
                self._log_fallback(label, next_label, e, error_class="permanent")

        logger.error(
            "llm_all_providers_failed",
            error=str(last_error),
            error_type=type(last_error).__name__ if last_error else None,
        )
        raise last_error

    @staticmethod
    def _log_fallback(
        from_provider: str,
        to_provider: str | None,
        error: Exception,
        error_class: str,
    ) -> None:
        """记录供应商切换日志（不落敏感信息）"""
        logger.warning(
            "llm_provider_fallback",
            from_provider=from_provider,
            to_provider=to_provider,
            error=str(error),
            error_class=error_class,
        )
    
    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector (async, non-blocking)
        
        Uses asyncio.to_thread to avoid blocking the event loop
        since the underlying embed_query uses synchronous requests.
        """
        try:
            # Ensure text is a clean string
            if not isinstance(text, str):
                logger.warning(
                    "embedding_input_type_warning",
                    original_type=type(text).__name__,
                    original_value=str(text)[:100]
                )
                text = str(text)
            
            # Remove any problematic characters
            text = text.strip()
            
            # Log before embedding call with more details
            logger.info(
                "embedding_generation_start",
                model=settings.LLM_EMBEDDING_API_MODEL_NAME,
                text_length=len(text),
                text_preview=text[:100],
                text_type=type(text).__name__,
                has_newlines='\n' in text,
                has_special_chars=any(c in text for c in ['{', '}', '[', ']'])
            )
            
            # Use asyncio.to_thread to avoid blocking the event loop
            result = await asyncio.to_thread(self.embedding_model.embed_query, text)
            
            # Log after embedding call
            logger.info(
                "embedding_generation_success",
                model=settings.LLM_EMBEDDING_API_MODEL_NAME,
                embedding_dimension=len(result)
            )
            
            return result
        except Exception as e:
            logger.error(
                "embedding_generation_failed",
                error=str(e),
                model=settings.LLM_EMBEDDING_API_MODEL_NAME,
                text_length=len(text) if 'text' in locals() else 0,
                text_preview=text[:100] if 'text' in locals() else "",
                error_type=type(e).__name__
            )
            raise
    
    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        try:
            # Log before batch embedding call
            logger.info(
                "batch_embedding_generation_start",
                model=settings.LLM_EMBEDDING_API_MODEL_NAME,
                text_count=len(texts),
                total_chars=sum(len(t) for t in texts)
            )
            
            result = self.embedding_model.embed_documents(texts)
            
            # Log after batch embedding call
            logger.info(
                "batch_embedding_generation_success",
                model=settings.LLM_EMBEDDING_API_MODEL_NAME,
                embeddings_count=len(result),
                embedding_dimension=len(result[0]) if result else 0
            )
            
            return result
        except Exception as e:
            logger.error("batch_embedding_generation_failed", error=str(e), model=settings.LLM_EMBEDDING_API_MODEL_NAME)
            raise
