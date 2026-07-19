"""
自定义阿里云 Embedding 实现
支持同步和异步调用，使用 httpx 避免阻塞事件循环
"""
import asyncio
import httpx
from typing import List, Optional
from langchain_core.embeddings import Embeddings
from app.utils.logger import get_logger

logger = get_logger()


class AliyunEmbeddings(Embeddings):
    """
    Custom embeddings for Aliyun DashScope
    
    Directly calls the DashScope API using requests, bypassing LangChain's
    OpenAI compatibility layer which may have parameter format issues.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: str = "text-embedding-v4",
        timeout: int = 30
    ):
        """
        Initialize Aliyun Embeddings
        
        Args:
            api_key: DashScope API key
            base_url: API base URL (compatible mode)
            model: Model name (default: text-embedding-v4)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self._async_client: Optional[httpx.AsyncClient] = None
        
        logger.info(
            "aliyun_embeddings_initialized",
            base_url=self.base_url,
            model=self.model
        )
    
    async def _get_async_client(self) -> httpx.AsyncClient:
        """Lazy initialization of async HTTP client"""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)
        return self._async_client
    
    async def aembed_query(self, text: str) -> List[float]:
        """
        Async version: Generate embedding for a single query text
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        # Clean and validate input
        if not isinstance(text, str):
            logger.warning(
                "embedding_input_type_warning",
                original_type=type(text).__name__,
                original_value=str(text)[:100]
            )
            text = str(text)
        
        text = text.strip()
        
        if not text:
            raise ValueError("Input text cannot be empty")
        
        # Prepare request
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "input": text,
            "encoding_format": "float"
        }
        
        try:
            # Log request details
            logger.info(
                "aliyun_embedding_request",
                url=url,
                model=self.model,
                text_length=len(text),
                text_preview=text[:100]
            )
            
            # Make async request
            client = await self._get_async_client()
            response = await client.post(url, headers=headers, json=payload)
            
            # Check response
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                logger.error(
                    "aliyun_embedding_api_error",
                    status_code=response.status_code,
                    error=response.text[:500]
                )
                raise Exception(error_msg)
            
            # Parse response
            result = response.json()
            
            if "data" not in result or len(result["data"]) == 0:
                raise ValueError("Invalid API response: no embedding data found")
            
            embedding = result["data"][0]["embedding"]
            
            # Log success
            logger.info(
                "aliyun_embedding_success",
                model=self.model,
                embedding_dimension=len(embedding)
            )
            
            return embedding
            
        except httpx.TimeoutException:
            logger.error(
                "aliyun_embedding_timeout",
                model=self.model,
                timeout=self.timeout
            )
            raise TimeoutError(f"Embedding API request timed out after {self.timeout}s")
            
        except httpx.ConnectError as e:
            logger.error(
                "aliyun_embedding_connection_error",
                model=self.model,
                error=str(e)
            )
            raise ConnectionError(f"Failed to connect to embedding API: {str(e)}")
            
        except Exception as e:
            logger.error(
                "aliyun_embedding_failed",
                model=self.model,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Async version: Generate embeddings for multiple documents concurrently
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors
        """
        logger.info(
            "aliyun_embedding_batch_start",
            model=self.model,
            document_count=len(texts)
        )
        
        # Process concurrently with asyncio.gather
        tasks = [self.aembed_query(text) for text in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        embeddings = []
        failed_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "aliyun_embedding_batch_item_failed",
                    index=i,
                    error=str(result)
                )
                failed_count += 1
            else:
                embeddings.append(result)
                if (i + 1) % 10 == 0:
                    logger.info(
                        "aliyun_embedding_batch_progress",
                        processed=i + 1,
                        total=len(texts)
                    )
        
        logger.info(
            "aliyun_embedding_batch_completed",
            successful=len(embeddings),
            failed=failed_count,
            total=len(texts)
        )
        
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """
        Sync version: Generate embedding for a single query text
        
        Note: This method uses synchronous requests and may block the event loop.
        For async contexts, use aembed_query() instead.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        import requests
        
        # Clean and validate input
        if not isinstance(text, str):
            logger.warning(
                "embedding_input_type_warning",
                original_type=type(text).__name__,
                original_value=str(text)[:100]
            )
            text = str(text)
        
        text = text.strip()
        
        if not text:
            raise ValueError("Input text cannot be empty")
        
        # Prepare request
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "input": text,  # Pass string directly (not list)
            "encoding_format": "float"
        }
        
        try:
            # Log request details
            logger.info(
                "aliyun_embedding_request",
                url=url,
                model=self.model,
                text_length=len(text),
                text_preview=text[:100]
            )
            
            # Make request
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            # Check response
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                logger.error(
                    "aliyun_embedding_api_error",
                    status_code=response.status_code,
                    error=response.text[:500]
                )
                raise Exception(error_msg)
            
            # Parse response
            result = response.json()
            
            if "data" not in result or len(result["data"]) == 0:
                raise ValueError("Invalid API response: no embedding data found")
            
            embedding = result["data"][0]["embedding"]
            
            # Log success
            logger.info(
                "aliyun_embedding_success",
                model=self.model,
                embedding_dimension=len(embedding)
            )
            
            return embedding
            
        except requests.exceptions.Timeout:
            logger.error(
                "aliyun_embedding_timeout",
                model=self.model,
                timeout=self.timeout
            )
            raise TimeoutError(f"Embedding API request timed out after {self.timeout}s")
            
        except requests.exceptions.ConnectionError as e:
            logger.error(
                "aliyun_embedding_connection_error",
                model=self.model,
                error=str(e)
            )
            raise ConnectionError(f"Failed to connect to embedding API: {str(e)}")
            
        except Exception as e:
            logger.error(
                "aliyun_embedding_failed",
                model=self.model,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Sync version: Generate embeddings for multiple documents
        
        Note: This method processes sequentially and may be slow for large batches.
        For better performance, use aembed_documents() which processes concurrently.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors
        """
        logger.info(
            "aliyun_embedding_batch_start",
            model=self.model,
            document_count=len(texts)
        )
        
        embeddings = []
        for i, text in enumerate(texts):
            try:
                embedding = self.embed_query(text)
                embeddings.append(embedding)
                
                if (i + 1) % 10 == 0:
                    logger.info(
                        "aliyun_embedding_batch_progress",
                        processed=i + 1,
                        total=len(texts)
                    )
                    
            except Exception as e:
                logger.error(
                    "aliyun_embedding_batch_item_failed",
                    index=i,
                    error=str(e)
                )
                # Continue with other documents
                embeddings.append(None)
        
        # Filter out failed embeddings
        successful = [e for e in embeddings if e is not None]
        failed_count = len([e for e in embeddings if e is None])
        
        logger.info(
            "aliyun_embedding_batch_completed",
            successful=len(successful),
            failed=failed_count,
            total=len(texts)
        )
        
        return successful
