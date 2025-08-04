from pymilvus import connections, Collection
from config.zilliz_config import config


class ZillizClient:
    def __init__(self):
        connections.connect(uri=config.endpoint, token=config.api_key)
        self.collection = Collection(config.collection_name)

    async def vector_search(self, embedding: list, top_k: int = 100):
        search_params = {"metric_type": "IP", "params": {"nprobe": 32}}  # 内积相似度
        return self.collection.search(
            data=[embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["job_id", "title", "company"],
        )

    async def hybrid_search(self, vector: list, filter_expr: str):
        # 混合查询（Zilliz 2.3+特性）
        return self.collection.search(
            data=[vector],
            anns_field="embedding",
            param={"nprobe": 32},
            limit=100,
            expr=filter_expr,  # 例如："graduation_year >= 2025 and job_type == '实习'"
        )
