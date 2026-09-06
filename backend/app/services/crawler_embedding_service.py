"""
爬虫专用的 Embedding 服务
支持同步和异步调用，使用 httpx 避免阻塞事件循环
"""
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

# dashscope text-embedding-v4 单条 input 有 token 上限（8192 tokens），
# 超长 JD（如 Greenhouse 2 万+字符）会报错。按字符截断（中文约 1~1.5 chars/token）
MAX_EMBEDDING_INPUT_CHARS = 12000


class CrawlerEmbeddingService:
    """爬虫专用的 embedding 服务，支持批处理"""
    
    def __init__(
        self,
        api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key: str = None,
        model: str = "text-embedding-v4",
        timeout: int = 30
    ):
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self._async_client: Optional[httpx.AsyncClient] = None
    
    async def _get_async_client(self) -> httpx.AsyncClient:
        """Lazy initialization of async HTTP client"""
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)
        return self._async_client
    
    async def aget_single_embedding(self, text: str) -> List[float]:
        """Async version: Get single text embedding"""
        text = text[:MAX_EMBEDDING_INPUT_CHARS]
        url = f"{self.api_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "input": text,
            "encoding_format": "float"
        }
        
        client = await self._get_async_client()
        response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"API request failed with status {response.status_code}: {response.text}")
        
        result = response.json()
        
        if "data" not in result or len(result["data"]) == 0:
            raise ValueError("Invalid API response: no embedding data found")
        
        return result["data"][0]["embedding"]
    
    async def aget_embedding_batch(
        self,
        input_file_path: str,
        output_file_path: str = "output.jsonl",
        concurrency: int = 5
    ) -> List[Dict]:
        """
        Async batch processing with concurrency control
        
        Args:
            input_file_path: Input JSONL file path
            output_file_path: Output file path
            concurrency: Max concurrent requests (default: 5)
            
        Returns:
            List of dicts with format: [{"id": str(uuid), "embedding": List[float]}]
        """
        try:
            # Read input file (sync is fine for file I/O)
            logger.info(f"Reading batch input file: {input_file_path}")
            with open(input_file_path, 'r', encoding='utf-8') as f:
                batch_requests = [json.loads(line) for line in f if line.strip()]
            
            logger.info(f"Processing {len(batch_requests)} items with concurrency={concurrency}")
            
            # Semaphore to limit concurrency
            semaphore = asyncio.Semaphore(concurrency)
            
            async def process_with_semaphore(batch_req):
                async with semaphore:
                    custom_id = batch_req.get('custom_id')
                    text_input = batch_req.get('body', {}).get('input', '')
                    
                    if not text_input:
                        logger.warning(f"Empty input for {custom_id}, skipping")
                        return None
                    
                    try:
                        embedding = await self.aget_single_embedding(text_input)
                        return {"id": custom_id, "embedding": embedding}
                    except Exception as e:
                        logger.error(f"Failed to process {custom_id}: {e}")
                        return None
            
            # Process concurrently
            tasks = [process_with_semaphore(req) for req in batch_requests]
            results_raw = await asyncio.gather(*tasks, return_exceptions=False)
            
            # Filter out None results
            results = [r for r in results_raw if r is not None]
            
            # Write output file
            logger.info(f"Writing {len(results)} results to {output_file_path}")
            with open(output_file_path, 'w', encoding='utf-8') as f:
                for result in results:
                    output_line = {
                        "custom_id": result["id"],
                        "response": {
                            "body": {
                                "data": [
                                    {
                                        "embedding": result["embedding"],
                                        "index": 0,
                                        "object": "embedding"
                                    }
                                ],
                                "model": self.model,
                                "object": "list",
                                "usage": {"prompt_tokens": 0, "total_tokens": 0}
                            }
                        }
                    }
                    f.write(json.dumps(output_line, ensure_ascii=False) + '\n')
            
            logger.info(f"Batch processing completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}", exc_info=True)
            raise
    
    def get_embedding_batch(
        self,
        input_file_path: str,
        output_file_path: str = "output.jsonl"
    ) -> List[Dict]:
        """
        批量生成 embeddings
        
        Args:
            input_file_path: 输入 JSONL 文件路径，格式为 OpenAI batch API 格式
            output_file_path: 输出文件路径
            
        Returns:
            List of dicts with format: [{"id": str(uuid), "embedding": List[float]}]
        """
        try:
            # 读取输入文件
            logger.info(f"Reading batch input file: {input_file_path}")
            with open(input_file_path, 'r', encoding='utf-8') as f:
                batch_requests = [json.loads(line) for line in f if line.strip()]
            
            logger.info(f"Processing {len(batch_requests)} items in batch")
            
            results = []
            for i, batch_req in enumerate(batch_requests):
                try:
                    custom_id = batch_req.get('custom_id')
                    text_input = batch_req.get('body', {}).get('input', '')
                    
                    if not text_input:
                        logger.warning(f"Empty input for item {i}, skipping")
                        continue
                    
                    # 调用 embedding API
                    embedding = self._get_single_embedding(text_input)
                    
                    results.append({
                        "id": custom_id,
                        "embedding": embedding
                    })
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"Processed {i + 1}/{len(batch_requests)} items")
                        
                except Exception as e:
                    logger.error(f"Failed to process item {i}: {e}")
                    continue
            
            # 写入输出文件
            logger.info(f"Writing {len(results)} results to {output_file_path}")
            with open(output_file_path, 'w', encoding='utf-8') as f:
                for result in results:
                    # 构造符合 OpenAI batch API 格式的输出
                    output_line = {
                        "custom_id": result["id"],
                        "response": {
                            "body": {
                                "data": [
                                    {
                                        "embedding": result["embedding"],
                                        "index": 0,
                                        "object": "embedding"
                                    }
                                ],
                                "model": self.model,
                                "object": "list",
                                "usage": {"prompt_tokens": 0, "total_tokens": 0}
                            }
                        }
                    }
                    f.write(json.dumps(output_line, ensure_ascii=False) + '\n')
            
            logger.info(f"Batch processing completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}", exc_info=True)
            raise
    
    def _get_single_embedding(self, text: str) -> List[float]:
        """Get single text embedding (sync version using httpx)"""
        text = text[:MAX_EMBEDDING_INPUT_CHARS]
        url = f"{self.api_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "input": text,
            "encoding_format": "float"
        }
        
        # Use httpx.Client for sync requests (better than requests)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"API request failed with status {response.status_code}: {response.text}")
        
        result = response.json()
        
        if "data" not in result or len(result["data"]) == 0:
            raise ValueError("Invalid API response: no embedding data found")
        
        return result["data"][0]["embedding"]
