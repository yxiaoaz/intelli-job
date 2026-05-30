from langchain.chat_models.base import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings
from app.utils.logger import get_logger

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
        
        # 使用 OpenAIEmbeddings 作为通用嵌入模型接口
        # 支持任何兼容 OpenAI 格式的嵌入模型
        self.embedding_model: Embeddings = OpenAIEmbeddings(
            model=settings.LLM_EMBEDDING_API_MODEL_NAME,
            dimensions=1024,
            api_key=settings.LLM_EMBEDDING_API_KEY,
            base_url=settings.LLM_EMBEDDING_API_URL,
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_completion(self, messages: list[dict]) -> str:
        """Generate completion with retry logic"""
        try:
            response = await self.chat_model.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error("llm_completion_failed", error=str(e))
            raise
    
    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector"""
        try:
            return self.embedding_model.embed_query(text)
        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            raise
    
    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        try:
            return self.embedding_model.embed_documents(texts)
        except Exception as e:
            logger.error("batch_embedding_generation_failed", error=str(e))
            raise
