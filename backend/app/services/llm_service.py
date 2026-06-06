from langchain.chat_models.base import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings
from app.utils.logger import get_logger
from app.services.aliyun_embeddings import AliyunEmbeddings

settings = get_settings()
logger = get_logger()


class LLMService:
    """Service for LLM operations using LangChain (model-agnostic)"""
    
    def __init__(self):
        # 使用 ChatOpenAI 作为通用聊天模型接口
        # 支持任何兼容 OpenAI API 格式的模型（DeepSeek, Qwen, Claude等）
        self.chat_model: BaseChatModel = ChatOpenAI(
            model=settings.LLM_COMPLETION_API_MODEL_NAME,
            temperature=0.7,
            api_key=settings.LLM_COMPLETION_API_KEY,
            base_url=settings.LLM_COMPLETION_API_URL,
        )
        
        # 使用自定义的 AliyunEmbeddings，直接调用 DashScope API
        # 绕过 LangChain 的 OpenAI 兼容层，避免参数格式问题
        self.embedding_model: Embeddings = AliyunEmbeddings(
            api_key=settings.LLM_EMBEDDING_API_KEY,
            base_url=settings.LLM_EMBEDDING_API_URL,
            model=settings.LLM_EMBEDDING_API_MODEL_NAME,
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_completion(self, messages: list[dict]) -> str:
        """Generate completion with retry logic"""
        try:
            # Log before LLM call
            message_count = len(messages)
            system_msg_preview = ""
            user_msg_preview = ""
            for msg in messages:
                if msg.get("role") == "system":
                    system_msg_preview = msg.get("content", "")[:100]
                elif msg.get("role") == "user":
                    user_msg_preview = msg.get("content", "")[:100]
            
            logger.info(
                "llm_call_start",
                model=settings.LLM_COMPLETION_API_MODEL_NAME,
                message_count=message_count,
                system_prompt_preview=system_msg_preview,
                user_prompt_preview=user_msg_preview
            )
            
            response = await self.chat_model.ainvoke(messages)
            result_content = response.content
            
            # Log after LLM call
            logger.info(
                "llm_call_success",
                model=settings.LLM_COMPLETION_API_MODEL_NAME,
                response_length=len(result_content) if isinstance(result_content, str) else 0,
                response_preview=result_content[:200] if isinstance(result_content, str) else ""
            )
            
            return result_content
        except Exception as e:
            logger.error("llm_completion_failed", error=str(e), model=settings.LLM_COMPLETION_API_MODEL_NAME)
            raise
    
    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector"""
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
            
            result = self.embedding_model.embed_query(text)
            
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
