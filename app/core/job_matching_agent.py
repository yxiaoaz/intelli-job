from typing import Any, List, Dict, Union
import uuid
import os
import json
import logging

from dotenv import load_dotenv
import numpy as np
from sqlalchemy import select
import redis

from app.config import get_project_root
from app.services.language_modeling.open_ai_service_provider import (
    OpenAIServiceProvider,
)
from app.services.storage.zilliz_controller import ZillizController
from app.services.storage.db_controller import DBController
from app.services.storage.engine import engine
from app.services.storage.utils import (
    session_scope,
    encode_embedding_for_redis,
    decode_embedding_from_redis,
)
from app.models.job import JobItem
from app.models.constant import RecruitmentType

# load .env
load_dotenv(os.path.join(get_project_root(), ".env"))

logger = logging.getLogger(__name__)

USER_EMBEDDING_CACHE_KEY = "user_embeddings"


class JobMatchingAgent:
    def __init__(self):
        self.vector_db_controller = ZillizController(
            uri=os.getenv("ZILLIZ_URI"), token=os.getenv("ZILLIZ_TOKEN")
        )
        self.db_controller = DBController(engine)
        self.embedding_service = OpenAIServiceProvider(
            api_url=os.getenv("LLM_EMBEDDING_API_URL"),
            api_key=os.getenv("LLM_EMBEDDING_API_KEY"),
        )
        self.redis_cache = redis.Redis(
            host=os.getenv("REDIS_HOST"),
            port=10771,
            decode_responses=True,
            username="default",
            password=os.getenv("REDIS_PASSWORD"),
        )  # cache for user embeddings

    def match_jobs(
        self,
        user_query_preference: Dict[str, Any],
        user_resume_profile: Dict[str, Any],
        search_mode: str = "hybrid",
        top_k: int = 100,
    ):

        # first filter by hard requirements
        print(
            f"Matching jobs with user query preference: {user_query_preference} and resume profile: {user_resume_profile}"
        )
        print(f"Search mode: {search_mode}, Top K: {top_k}")
        hard_filtered_job_items = self._filter_hard_requirements(user_query_preference)
        id_search_scope = [str(item.id) for item in hard_filtered_job_items]
        filter = (
            f"id IN {id_search_scope}" if id_search_scope else ""
        )  # check https://docs.zilliz.com/docs/filtering-overview for filter syntax in Zilliz

        # then do semantic/sparse/hybrid search
        # format user input string for sparse search
        user_input_str = self._format_user_input_str(
            user_query_preference, user_resume_profile
        )
        if search_mode == "semantic":
            user_embedding = self._get_user_embedding(user_input_str)
            res = self._get_semantic_search_results(
                user_embedding, top_k=top_k, filter=filter
            )
        elif search_mode == "sparse":
            res = self._get_sparse_search_results(
                user_input_str, top_k=top_k, filter=filter
            )
        elif search_mode == "hybrid":
            user_embedding = self._get_user_embedding(user_input_str)
            res = self._get_hybrid_search_results(
                user_embedding,
                user_input_str,
                top_k=top_k,
                filter=filter,
            )
        else:
            raise ValueError(f"Unsupported search mode: {search_mode}")

        print("Obtanined search results from Zilliz")
        res = self._postprocess_search_res(res)
        print(f"Post-processed search results: {len(res)} items found")

        # result format:
        # [{"job_Item": JobItem, "score": float},...]
        return res

    def _get_user_embedding(self, user_input_str: str) -> List[float]:
        """
        Retrieve or compute the user's embedding vector.
        If the embedding is cached in redis, retrieve it; otherwise, compute it and cache it in redis.
        """
        print("Looking for user embedding")
        user_input_hash = str(uuid.uuid3(uuid.NAMESPACE_DNS, user_input_str))
        if self.redis_cache.hexists(USER_EMBEDDING_CACHE_KEY, user_input_hash):
            user_embedding = decode_embedding_from_redis(
                self.redis_cache.hget(USER_EMBEDDING_CACHE_KEY, user_input_hash)
            )
            print("Found user embedding in cache")
            return user_embedding

        user_embedding = self.embedding_service.get_embedding(
            model_name="text-embedding-v4",
            input_txt=user_input_str,
            dimensions=1024,
        )[0]

        print("Computed user embedding, caching it")
        self.redis_cache.hset(
            USER_EMBEDDING_CACHE_KEY,
            user_input_hash,
            encode_embedding_for_redis(user_embedding),
        )

        return user_embedding

    def _format_user_input_str(
        self,
        user_query_preference: Dict[str, Any],
        user_resume_profile: Dict[str, Any],
    ):
        """
        Format user input string for sparse search.
        Combine user query preferences and resume profile into a single string.
        """
        res_dict = {
            "求职意愿 (job intention)": {
                "描述 (description)": "这是当前用户的求职意愿描述 (This is the user's job intention description)",
                "数据 (content)": user_query_preference,
            },
            "简历信息 (resume information)": {
                "描述 (description)": "这是当前用户的简历信息，主要体现用户的能力和背景 (This is the user's resume information, mainly reflecting the user's skills and background)",
                "数据 (content)": user_resume_profile,
            },
        }

        return json.dumps(res_dict, ensure_ascii=False, indent=2)

    def _filter_hard_requirements(
        self, user_query_preference: Dict[str, Any]
    ) -> List[JobItem]:
        """
        Filter job items based on hard requirements from user query preferences.
        """
        recruitment_type_str_to_enum = {
            "社招": RecruitmentType.EXPERIENCED,
            "校招": RecruitmentType.GRADUATE,
            "实习": RecruitmentType.INTERN,
        }
        intended_recruitment_types = [
            recruitment_type_str_to_enum[str_rec_type]
            for str_rec_type in user_query_preference.get("recruitment_type", [])
            if str_rec_type in recruitment_type_str_to_enum
        ]

        # seems to have some issue in identifying intern and graduate jobs
        # for a quick fix make sure these two always appear together
        if RecruitmentType.INTERN in intended_recruitment_types:
            intended_recruitment_types.append(RecruitmentType.GRADUATE)
        if RecruitmentType.GRADUATE in intended_recruitment_types:
            intended_recruitment_types.append(RecruitmentType.INTERN)
        
        intended_recruitment_types = list(set(intended_recruitment_types))

        with session_scope(self.db_controller.session_maker) as session:
            filtered_job_items = self.db_controller.filter_job_item_recruitment_type(
                session, intended_recruitment_types
            )
            session.expunge_all()

        return filtered_job_items

    def _postprocess_search_res(self, res: List[Dict]) -> List[Dict]:
        """
        Post-process the search results from Zilliz to extract job items and their scores.

        :param res: List of search results from Zilliz, format is [{"id": str(uuid), "distance":float}, ...],
        sorted by "distance" field (it is actually the similarity score) by descending order

        :return: List of dictionaries with job items and their scores, format is [{"job_item": JobItem, "score": float}, ...]
        """

        hit_scores = [
            j["distance"] for j in res
        ]  # if using cosine sim/inner product, the 'distance' is actually the similarity score
        hit_ids = [j["id"] for j in res]

        # get the corresponding job items from the database
        hit_job_items_id_map: Dict[uuid.UUID, JobItem] = {}
        with session_scope(self.db_controller.session_maker) as session:
            hit_job_items = (
                session.execute(select(JobItem).where(JobItem.id.in_(hit_ids)))
                .scalars()
                .all()
            )

            hit_job_items_id_map = {item.id: item for item in hit_job_items}

            session.expunge_all()

        # result format:
        # [{"job_Item": JobItem, "score": float},...]
        # sorted by hit score in descending order
        vector_search_res = [
            {
                "job_item": hit_job_items_id_map[uuid.UUID(hit_ids[i])],
                "score": hit_scores[i],
            }
            for i in range(len(hit_ids))
        ]

        return vector_search_res

    def _get_semantic_search_results(
        self,
        user_embedding: Union[List[float], List[List[float]]],
        top_k: int = 100,
        filter: str = "",
    ) -> List[Dict]:
        """Perform semantic search using the user's embedding vector."""

        # embedding search in vector db
        search_params = {
            "metric_type": "COSINE",
            "params": {
                "radius": 0.3,
            },
        }

        return self.vector_db_controller.search_job_item_semantic(
            user_embedding, search_params=search_params, top_k=top_k, filter=filter
        )[0]

    def _get_sparse_search_results(
        self, user_query: str, top_k: int = 100, filter: str = ""
    ) -> List[Dict]:
        """Perform sparse search using the user's query text."""

        search_params = {"params": {"level": 10}}

        return self.vector_db_controller.search_job_item_sparse(
            user_query, search_params=search_params, top_k=top_k, filter=filter
        )[0]

    def _get_hybrid_search_results(
        self,
        user_embedding: Union[List[float], List[List[float]]],
        user_query: str,
        top_k: int = 100,
        filter: str = "",
    ) -> List[Dict]:
        """Perform hybrid search using both embedding and query text."""

        search_param_semantic = {
            "metric_type": "COSINE",
            "params": {
                "radius": 0.3,
            },
        }
        search_param_sparse = {"params": {"level": 10}}

        return self.vector_db_controller.search_job_item_hybrid(
            embedding=user_embedding,
            text=user_query,
            search_param_semantic=search_param_semantic,
            search_param_sparse=search_param_sparse,
            top_k=top_k,
            filter=filter,
        )[0]
