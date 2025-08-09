# -*- coding: utf-8 -*-
__author__ = "yicong.xiao"

import os
from typing import Any, Dict, List, Union

from dotenv import load_dotenv
from pymilvus import MilvusClient

from app.config import get_project_root

# load .env
load_dotenv(os.path.join(get_project_root(), ".env"))


class ZillizController:
    def __init__(self, uri: str, token: str):
        self.client = MilvusClient(
            uri=uri, token=token
        )

        self.job_items_vector_collection = os.getenv("ZILLIZ_JOB_ITEM_COLLECTION_NAME")

    def insert_job_items(self, job_item_data: List[Dict[str, Any]]):
        """
        Insert a batch of job item embeddings.

        :param job_item_data: A mapping of **string** uuid to embedding.
        """
        return self.client.insert(
            collection_name=self.job_items_vector_collection , data=job_item_data
        )

    def search_job_item(self, 
                      embedding: Union[List[list], list], 
                      search_params: Dict[str, Any] = {"metric_type": "IP"}, 
                      top_k: int = 100):
        
        return self.client.search(
            collection_name=self.job_items_vector_collection,
            data=embedding,
            anns_field="embedding",
            search_params=search_params,
            limit=top_k,
        )

    def hybrid_search(self, vector: list, filter_expr: str):
        # 混合查询（Zilliz 2.3+特性）
        return self.collection.search(
            data=[vector],
            anns_field="embedding",
            param={"nprobe": 32},
            limit=100,
            expr=filter_expr,  # 例如："graduation_year >= 2025 and job_type == '实习'"
        )
