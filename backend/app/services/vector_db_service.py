from pymilvus import AnnSearchRequest, RRFRanker
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger()

# Milvus content 字段 VARCHAR max_length=10000（预留余量）
MAX_CONTENT_LENGTH = 9000


class VectorDBService:
    """Service for Zilliz vector database operations"""
    
    def __init__(self):
        from pymilvus import MilvusClient
        logger.info(f"Initializing VectorDBService - URI: {settings.ZILLIZ_URI}")
        self.client = MilvusClient(
            uri=settings.ZILLIZ_URI,
            token=settings.ZILLIZ_TOKEN,
            timeout=10,  # 连接超时 10 秒
        )
        self.collection_name = settings.ZILLIZ_JOB_ITEM_COLLECTION_NAME
        logger.info("VectorDBService initialized successfully")
    
    def search_semantic(
        self,
        embedding: list[float],
        top_k: int = 100,
        filter_expr: str = ""
    ) -> list[dict]:
        """Semantic search using dense embeddings (HNSW index)"""
        try:
            search_params = {
                "metric_type": "COSINE",
                "params": {
                    "radius": 0,
                    "ef": 100  # HNSW search parameter, balance speed and recall
                }
            }
            
            results = self.client.search(
                collection_name=self.collection_name,
                data=[embedding],
                anns_field="embedding",
                search_params=search_params,
                limit=top_k,
                filter=filter_expr
            )
            return results[0] if results else []
        except Exception as e:
            logger.error("semantic_search_failed", error=str(e))
            raise
    
    def search_sparse(
        self,
        text: str,
        top_k: int = 100,
        filter_expr: str = ""
    ) -> list[dict]:
        """Sparse search using BM25"""
        try:
            search_params = {
                "params": {
                    "level": 10  # BM25 search parameter
                }
            }
            
            results = self.client.search(
                collection_name=self.collection_name,
                data=[text],
                anns_field="sparse_vector",
                search_params=search_params,
                limit=top_k,
                filter=filter_expr
            )
            return results[0] if results else []
        except Exception as e:
            logger.error("sparse_search_failed", error=str(e))
            raise
    
    def search_hybrid(
        self,
        embedding: list[float],
        text: str,
        top_k: int = 100,
        filter_expr: str = ""
    ) -> list[dict]:
        """Hybrid search combining semantic (HNSW) and sparse (BM25)"""
        try:
            # Dense search request (HNSW)
            dense_request = AnnSearchRequest(
                data=[embedding],
                anns_field="embedding",
                param={
                    "metric_type": "COSINE",
                    "params": {
                        "radius": 0,
                        "ef": 100  # HNSW search parameter
                    }
                },
                limit=top_k,
                expr=filter_expr
            )
            
            # Sparse search request (BM25)
            sparse_request = AnnSearchRequest(
                data=[text],
                anns_field="sparse_vector",
                param={
                    "params": {
                        "level": 10  # BM25 search parameter
                    }
                },
                limit=top_k,
                expr=filter_expr
            )
            
            # RRF reranker
            ranker = RRFRanker(100)
            
            results = self.client.hybrid_search(
                collection_name=self.collection_name,
                reqs=[dense_request, sparse_request],
                ranker=ranker,
                limit=top_k
            )
            return results[0] if results else []
        except Exception as e:
            logger.error("hybrid_search_failed", error=str(e))
            raise
    
    def insert_embeddings(self, data: list[dict]) -> dict:
        """Insert embeddings into collection"""
        try:
            # Milvus content 字段 VARCHAR 上限 10000：ATS 源完整 JD 会超限，
            # 插入前截断（仅影响 BM25 稀疏向量的原文，embedding 向量不受影响）
            for item in data:
                content = item.get("content") or ""
                if len(content) > MAX_CONTENT_LENGTH:
                    item["content"] = content[:MAX_CONTENT_LENGTH]
            return self.client.insert(
                collection_name=self.collection_name,
                data=data
            )
        except Exception as e:
            logger.error("embedding_insertion_failed", error=str(e))
            raise

    def delete_embeddings_by_ids(self, ids: list) -> None:
        """按主键批量删除向量（指纹回填去重时清理已删岗位）。

        分批执行，避免过滤表达式过长；不存在的 id 无副作用。
        """
        if not ids:
            return
        try:
            id_strs = [str(i) for i in ids]
            batch_size = 500
            for start in range(0, len(id_strs), batch_size):
                batch = id_strs[start:start + batch_size]
                id_list = ", ".join(f'"{i}"' for i in batch)
                self.client.delete(
                    collection_name=self.collection_name,
                    filter=f"id in [{id_list}]",
                )
            logger.info(f"deleted_embeddings_from_vector_db count={len(id_strs)}")
        except Exception as e:
            logger.error("embedding_deletion_failed", error=str(e))
            raise
