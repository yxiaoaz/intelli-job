# -*- coding: utf-8 -*-
__author__ = "yicong.xiao"

import os
from typing import Any, Dict, List, Union

from dotenv import load_dotenv
from pymilvus import AnnSearchRequest, MilvusClient, RRFRanker

from app.config import get_project_root

# load .env
load_dotenv(os.path.join(get_project_root(), ".env"))


class ZillizController:
    def __init__(self, uri: str, token: str):
        self.client = MilvusClient(uri=uri, token=token)

        self.job_items_vector_collection = os.getenv("ZILLIZ_JOB_ITEM_COLLECTION_NAME")

    def insert_job_items(self, job_item_data: List[Dict[str, Any]]):
        """
        Insert a batch of job item embeddings.

        :param job_item_data: A mapping of **string** uuid to embedding.
        """
        return self.client.insert(
            collection_name=self.job_items_vector_collection, data=job_item_data
        )

    def search_job_item_semantic(
        self,
        embedding: Union[List[list], list],
        search_params: Dict[str, Any] = {"metric_type": "IP"},
        top_k: int = 100,
        filter: str = "",
    ):

        return self.client.search(
            collection_name=self.job_items_vector_collection,
            data=embedding,
            anns_field="embedding",
            search_params=search_params,
            limit=top_k,
            filter=filter,
        )

    def search_job_item_sparse(
        self, 
        text: str,
        search_params: Dict[str, Any] = {'params': {'level': 10}},
        top_k: int = 100,
        filter: str = "",
    ):
        return self.client.search(
            collection_name=self.job_items_vector_collection,
            data=[text],
            anns_field="content",
            search_params=search_params,
            limit=top_k,
            filter=filter,
        )
        

    def search_job_item_hybrid(
        self,
        embedding: list,
        text: str,
        search_param_semantic: Dict[str, Any],
        search_param_sparse: Dict[str, Any],
        top_k: int = 100,
        filter: str = "",
    ):

        # text semantic search (dense)
        search_param_1 = {
            "data": [embedding],
            "anns_field": "embedding",
            "param": search_param_semantic,
            "limit": top_k,
            "filter": filter,
        }
        request_1 = AnnSearchRequest(**search_param_1)

        # full-text search (sparse)
        search_param_2 = {
            "data": [text],
            "anns_field": "content",
            "param": search_param_sparse,
            "limit": top_k,
            "filter": filter,
        }
        request_2 = AnnSearchRequest(**search_param_2)

        # reranker based on ranking
        ranker = RRFRanker(100)

        return self.client.hybrid_search(
            collection_name=self.job_items_vector_collection,
            reqs=[request_1, request_2],
            ranker=ranker,
            limit=top_k,
        )
