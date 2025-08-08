from typing import List, Dict, Union
from uuid import UUID
import os

import numpy as np
from sqlalchemy import select

from app.services.language_modeling.open_ai_service_provider import OpenAIServiceProvider
from app.services.storage.zilliz_controller import ZillizController
from app.services.storage.db_controller import DBController
from app.services.storage.engine import engine
from app.services.storage.utils import session_scope
from app.models.job import JobItem


class JobMatchingAgent:
    def __init__(self):
        self.vector_db_controller = ZillizController(uri=os.getenv("ZILLIZ_URI"), token=os.getenv("ZILLIZ_TOKEN"))
        self.db_controller = DBController(engine)
        self.embedding_service = OpenAIServiceProvider(
            api_url=os.getenv("LLM_EMBEDDING_API_URL"),
            api_key=os.getenv("LLM_EMBEDDING_API_KEY"),
        )
        self.cache = {}  # 用于缓存用户embedding

    def match_jobs(self, user_profile: Dict) -> List[Dict]:
        # 生成用户表征向量（带缓存）
        user_embedding = self._get_user_embedding(user_profile)

        # 混合检索
        if user_profile.get("strict_filters"):
            # 带条件过滤的混合搜索
            filter_expr = self._build_filter_expr(user_profile)
            results = self.zilliz.hybrid_search(user_embedding, filter_expr)
        else:
            # 纯向量搜索
            results = self._get_semantic_search_results(user_embedding)

        # 精排
        scored_jobs = self._rerank(results, user_profile)
        return sorted(scored_jobs, key=lambda x: x["score"], reverse=True)[:50]
    
    def _get_semantic_search_results(self, user_embedding: Union[List[float], List[List[float]]]) -> List[Dict]:
        """Perform semantic search using the user's embedding vector."""

        # embedding search in vector db
        search_params = {
            "metric_type": "COSINE",
            "params": {
                "radius": 0.3,
            }
        }

        res = self.vector_db_controller.search_job_item(user_embedding, search_params=search_params, top_k=100)
        hit_scores = [j['distance'] for j in res[0]]  # if using cosine sim/inner product, the 'distance' is actually the similarity score
        hit_ids = [j['id'] for j in res[0]]

        # get the corresponding job items from the database
        # sort by hit score 
        hit_job_items_id_map:Dict[UUID, JobItem] = {}
        with session_scope(self.db_controller.session_maker) as session:
            hit_job_items = session.execute(
                select(JobItem).where(JobItem.id.in_(hit_ids))
            ).scalars().all()

            hit_job_items_id_map = {item.id: item for item in hit_job_items}

            session.expunge_all()

        # result format:
        # [{"job_Item": JobItem, "score": float},...]
        vector_search_res = [{"job_item":hit_job_items_id_map[UUID(hit_ids[i])], "score":hit_scores[i]} for i in range(len(hit_ids))]

        return vector_search_res

    def _get_user_embedding(self, profile: Dict) -> List[float]:
        """生成用户画像的向量表征"""
        cache_key = f"{profile['user_id']}_embed"
        if cache_key not in self.cache:
            text = self._format_profile_text(profile)
            self.cache[cache_key] = self.embedding_service.get_embedding(input_txt=text)
        return self.cache[cache_key]

    def _build_filter_expr(self, profile: Dict) -> str:
        """构建Zilliz过滤表达式"""
        filters = []
        if "graduation_year" in profile:
            filters.append(f"graduation_year >= {profile['graduation_year'] - 1}")
        if "job_type" in profile:
            types = ",".join([f"'{t}'" for t in profile["job_type"]])
            filters.append(f"job_type in [{types}]")
        return " and ".join(filters)

    def _format_profile_text(self, profile: Dict) -> str:
        """格式化用户画像文本用于生成embedding"""
        skills = ", ".join(profile.get("skills", []))
        exp = "\n".join(
            [
                f"{e['position']}@{e['company']}: {e['responsibilities']}"
                for e in profile.get("work_experience", [])
            ]
        )
        return f"Skills: {skills}\nExperience:\n{exp}"

    def _rerank(self, raw_results: List, profile: Dict) -> List[Dict]:
        """混合精排策略"""
        reranked = []
        for hit in raw_results[0]:  # Zilliz返回结构
            job = hit.entity
            base_score = hit.score  # 向量相似度基础分

            # 增加业务规则权重
            bonus = 0
            if self._is_campus_job(job) and profile.get("is_fresh_graduate"):
                bonus += 0.2
            if self._location_match(job, profile.get("intended_location")):
                bonus += 0.15

            reranked.append(
                {
                    "job_id": job.job_id,
                    "title": job.title,
                    "company": job.company,
                    "score": min(base_score + bonus, 1.0),  # 确保不超过1.0
                }
            )
        return reranked

    def _is_campus_job(self, job) -> bool:
        return "校招" in job.title or "应届" in job.description

    def _location_match(self, job, locations: List[str]) -> bool:
        return any(loc in job.location for loc in locations)
