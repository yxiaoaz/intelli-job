from typing import List, Dict
from services.zilliz_client import ZillizClient
from services.language_modeling import EmbeddingService
import numpy as np


class JobMatchingAgent:
    def __init__(self):
        self.zilliz = ZillizClient()
        self.embedder = EmbeddingService()
        self.cache = {}  # 用于缓存用户embedding

    async def match_jobs(self, user_profile: Dict) -> List[Dict]:
        # 生成用户表征向量（带缓存）
        user_embed = await self._get_user_embedding(user_profile)

        # 混合检索
        if user_profile.get("strict_filters"):
            # 带条件过滤的混合搜索
            filter_expr = self._build_filter_expr(user_profile)
            results = await self.zilliz.hybrid_search(user_embed, filter_expr)
        else:
            # 纯向量搜索
            results = await self.zilliz.vector_search(user_embed)

        # 精排
        scored_jobs = await self._rerank(results, user_profile)
        return sorted(scored_jobs, key=lambda x: x["score"], reverse=True)[:50]

    async def _get_user_embedding(self, profile: Dict) -> List[float]:
        """生成用户画像的向量表征"""
        cache_key = f"{profile['user_id']}_embed"
        if cache_key not in self.cache:
            text = self._format_profile_text(profile)
            self.cache[cache_key] = await self.embedder.generate(text)
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

    async def _rerank(self, raw_results: List, profile: Dict) -> List[Dict]:
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
