import asyncio
import hashlib
import json
import time
import uuid
from datetime import datetime
from typing import Any
from app.services.llm_service import LLMService
from app.services.vector_db_service import VectorDBService
from app.repositories.job_repo import JobRepository
from app.models.constants import RecruitmentType
from app.utils.logger import get_logger

logger = get_logger()


class JobMatchingService:
    """Service for job matching using hybrid search"""
    
    _recall_cache: dict[str, dict] = {}  # key -> {"results": [...], "ts": float}
    _recall_cache_ttl: float = 600.0  # 10 分钟

    def __init__(self):
        self.llm_service = LLMService()
        self.vector_db_service = VectorDBService()
    
    async def match_jobs(
        self,
        user_query_preference: dict[str, Any],
        user_resume_profile: dict[str, Any],
        search_mode: str = "hybrid",
        top_k: int = 100,
        hard_filters: dict[str, Any] | None = None,
        job_repo: JobRepository = None,
        skip_enhancement: bool = False,
    ) -> list[dict]:
        """
        Match jobs based on user preferences and resume
        
        Args:
            user_query_preference: User's job search preferences
            user_resume_profile: Parsed resume information
            search_mode: "semantic", "sparse", or "hybrid"
            top_k: Number of results to return
            hard_filters: Hard requirements (e.g., recruitment_type)
            job_repo: Job repository for database operations
            skip_enhancement: 已废弃，保留参数兼容。query 增强已移至调用方（QueryFormulator）
            
        Returns:
            List of matched jobs with scores
        """
        if hard_filters is None:
            hard_filters = {}
        logger.info(
            "job_matching_started",
            search_mode=search_mode,
            top_k=top_k,
            has_filters=len(hard_filters) > 0,
            skip_enhancement=skip_enhancement
        )
        
        # Step 1: 分流 —— 有 expanded_query 走向量, 没有走纯 SQL
        expanded_query = (user_query_preference or {}).get("keywords", "").strip()
        
        if not expanded_query:
            # 纯精确搜索: 直接 SQL 过滤, 不跑 LLM/Milvus
            if not hard_filters or not job_repo:
                return []
            filtered_ids = await job_repo.filter_by_hard_conditions(
                recruitment_types=hard_filters.get('recruitment_type'),
                min_education=hard_filters.get('education_level'),
                update_time_after=hard_filters.get('update_time_after'),
                update_time_before=hard_filters.get('update_time_before'),
                company=hard_filters.get('company'),
                city=hard_filters.get('city'),
                job_keyword=hard_filters.get('job_keyword'),
            )
            if not filtered_ids:
                return []
            jobs = await job_repo.get_by_ids([uuid.UUID(jid) for jid in filtered_ids])
            jobs.sort(key=lambda j: j.update_time or datetime.min, reverse=True)
            logger.info("pure_sql_search_completed", result_count=len(jobs))
            return [{"job_item": j, "score": 0.0} for j in jobs[:top_k]]
        
        # Step 2: 智能搜索 — L2 缓存检查
        user_input_str = self._format_user_input(user_query_preference, user_resume_profile)
        recall_key = self._build_recall_key(expanded_query, top_k)
        cached = self._get_cached_recall(recall_key)
        results = None
        
        if cached:
            results = cached
            logger.info("vector_recall_cache_hit", key=recall_key[:32])
        else:
            # Step 3: Milvus 裸召回 (filter_expr="")
            normalized_mode = search_mode.lower()
            if normalized_mode in ["keyword", "fulltext"]:
                normalized_mode = "sparse"
            elif normalized_mode == "vector":
                normalized_mode = "semantic"
            
            logger.info(
                "user_input_formatted",
                search_mode=search_mode,
                input_length=len(user_input_str),
                input_preview=user_input_str[:200]
            )
            
            if normalized_mode == "semantic":
                logger.info("starting_semantic_search")
                user_embedding = await self.llm_service.generate_embedding(user_input_str)
                results = await asyncio.to_thread(
                    self.vector_db_service.search_semantic,
                    embedding=user_embedding,
                    top_k=top_k,
                    filter_expr=""
                )
                logger.info("semantic_search_completed", result_count=len(results) if results else 0)
            elif normalized_mode == "sparse":
                logger.info("starting_sparse_search")
                results = await asyncio.to_thread(
                    self.vector_db_service.search_sparse,
                    text=user_input_str,
                    top_k=top_k,
                    filter_expr=""
                )
                logger.info("sparse_search_completed", result_count=len(results) if results else 0)
            elif normalized_mode == "hybrid":
                logger.info("starting_hybrid_search")
                user_embedding = await self.llm_service.generate_embedding(user_input_str)
                results = await asyncio.to_thread(
                    self.vector_db_service.search_hybrid,
                    embedding=user_embedding,
                    text=user_input_str,
                    top_k=top_k,
                    filter_expr=""
                )
                logger.info("hybrid_search_completed", result_count=len(results) if results else 0)
            else:
                raise ValueError(f"Unsupported search mode: {search_mode}. Supported modes: semantic, sparse/keyword/fulltext, hybrid")
            
            # 写 L2 缓存
            self._set_cached_recall(recall_key, results)
            logger.info("vector_recall_cache_miss", key=recall_key[:32])
        
        # Step 4: 后置 SQL 过滤
        if hard_filters:
            results = await self._post_filter_results(results, hard_filters, job_repo)
        
        # Step 5: Post-process results
        processed_results = await self._postprocess_results(results, job_repo)
        
        logger.info("job_matching_completed", result_count=len(processed_results))
        return processed_results
    
    async def _apply_hard_filters(
        self, 
        hard_filters: dict[str, Any],
        job_repo: JobRepository
    ) -> list[str]:
        """Apply hard filters and return filtered job IDs
        
        支持的过滤条件：
        - recruitment_type: 招聘类型列表
        - education_level: 最低学历要求
        - update_time_after: 更新时间下限（ISO格式字符串）
        - update_time_before: 更新时间上限（ISO格式字符串）
        """
        if not job_repo:
            return []
        
        # 如果没有任何硬过滤条件，返回空列表表示不过滤
        if not any(key in hard_filters for key in ['recruitment_type', 'education_level', 'update_time_after', 'update_time_before']):
            return []
        
        # 调用 Repository 层的过滤方法
        filtered_job_ids = await job_repo.filter_by_hard_conditions(
            recruitment_types=hard_filters.get('recruitment_type'),
            min_education=hard_filters.get('education_level'),
            update_time_after=hard_filters.get('update_time_after'),
            update_time_before=hard_filters.get('update_time_before')
        )
        
        logger.info(
            "hard_filters_applied",
            recruitment_type=hard_filters.get('recruitment_type'),
            education_level=hard_filters.get('education_level'),
            update_time_after=hard_filters.get('update_time_after'),
            update_time_before=hard_filters.get('update_time_before'),
            filtered_count=len(filtered_job_ids)
        )
        
        return filtered_job_ids
    
    async def _post_filter_results(
        self,
        raw_results: list[dict],
        hard_filters: dict[str, Any],
        job_repo: JobRepository,
    ) -> list[dict]:
        """对 Milvus 召回结果做 SQL 二次过滤（保持 score 排序）"""
        if not hard_filters or not raw_results or not job_repo:
            return raw_results
        hit_ids = [r["id"] for r in raw_results]
        filtered_ids = await job_repo.filter_by_hard_conditions(
            ids=hit_ids,
            recruitment_types=hard_filters.get("recruitment_type"),
            min_education=hard_filters.get("education_level"),
            update_time_after=hard_filters.get("update_time_after"),
            update_time_before=hard_filters.get("update_time_before"),
            company=hard_filters.get("company"),
            city=hard_filters.get("city"),
            job_keyword=hard_filters.get("job_keyword"),
        )
        filtered_set = set(filtered_ids)
        result = [r for r in raw_results if r["id"] in filtered_set]
        logger.info(
            "post_filter_completed",
            before_count=len(raw_results),
            after_count=len(result),
        )
        return result
    
    def _build_recall_key(self, expanded_query: str, top_k: int) -> str:
        return f"{hashlib.md5(expanded_query.encode()).hexdigest()}|{top_k}"

    def _get_cached_recall(self, key: str) -> list[dict] | None:
        entry = self._recall_cache.get(key)
        if not entry:
            return None
        if time.time() - entry["ts"] > self._recall_cache_ttl:
            del self._recall_cache[key]
            return None
        return entry["results"]

    def _set_cached_recall(self, key: str, results: list[dict]) -> None:
        self._recall_cache[key] = {"results": results, "ts": time.time()}
    
    def _format_user_input(
        self,
        user_query_preference: dict[str, Any],
        user_resume_profile: dict[str, Any]
    ) -> str:
        """Format user input for embedding generation
        
        Converts structured data to plain text format suitable for embedding APIs.
        Avoids JSON formatting characters that some embedding APIs don't accept.
        """
        # Build plain text representation
        parts = []
        
        # Add job intention
        if user_query_preference:
            parts.append("求职偏好:")
            for key, value in user_query_preference.items():
                if isinstance(value, dict):
                    parts.append(f"  {key}: {', '.join(str(v) for v in value.values())}")
                else:
                    parts.append(f"  {key}: {value}")
        
        # Add resume information
        if user_resume_profile:
            parts.append("\n简历信息:")
            # Handle different resume profile structures
            if isinstance(user_resume_profile, dict):
                for section, content in user_resume_profile.items():
                    if isinstance(content, list):
                        parts.append(f"  {section}: {', '.join(str(item) for item in content)}")
                    elif isinstance(content, dict):
                        parts.append(f"  {section}: {', '.join(str(v) for v in content.values())}")
                    else:
                        parts.append(f"  {section}: {content}")
            else:
                parts.append(f"  {user_resume_profile}")
        
        # Join with spaces, remove extra whitespace
        result = ' '.join(parts)
        
        # Log the formatted text for debugging
        logger.info(
            "user_input_formatted_for_embedding",
            original_length=len(json.dumps({"preference": user_query_preference, "resume": user_resume_profile})),
            formatted_length=len(result),
            preview=result[:200]
        )
        
        return result
    
    async def _postprocess_results(
        self,
        raw_results: list[dict],
        job_repo: JobRepository
    ) -> list[dict]:
        """Post-process search results"""
        if not raw_results:
            logger.info("postprocess_skip", reason="no_raw_results")
            return []
        
        logger.info(
            "postprocess_start",
            raw_result_count=len(raw_results),
            has_job_repo=job_repo is not None,
            first_result_id=raw_results[0].get("id") if raw_results else None
        )
        
        try:
            hit_ids = [uuid.UUID(result["id"]) for result in raw_results]
            hit_scores = [result["distance"] for result in raw_results]
            
            logger.info(
                "postprocess_ids_extracted",
                hit_ids=[str(hid) for hid in hit_ids[:3]],  # Log first 3 IDs
                total_ids=len(hit_ids)
            )
        except Exception as e:
            logger.error(
                "postprocess_uuid_conversion_failed",
                error=str(e),
                error_type=type(e).__name__,
                sample_result=raw_results[0] if raw_results else None
            )
            return []
        
        # Fetch job details from database
        if job_repo:
            try:
                jobs = await job_repo.get_by_ids(hit_ids)
                job_map = {job.id: job for job in jobs}
                
                logger.info(
                    "postprocess_jobs_fetched",
                    requested_count=len(hit_ids),
                    fetched_count=len(jobs),
                    missing_count=len(hit_ids) - len(jobs),
                    fetched_ids=[str(job.id) for job in jobs[:3]]  # Log first 3
                )
            except Exception as e:
                logger.error(
                    "postprocess_fetch_jobs_failed",
                    error=str(e),
                    error_type=type(e).__name__
                )
                job_map = {}
        else:
            logger.warning("postprocess_no_job_repo", reason="job_repo_is_none")
            job_map = {}
        
        # Build response
        processed = []
        missing_jobs = []
        invalid_jobs = []
        for i, job_id in enumerate(hit_ids):
            job = job_map.get(job_id)
            if job:
                # 兜底过滤：排除岗位名称和公司名称都未知的无效记录
                if job.job_title == "未知" and job.company_name == "未知":
                    invalid_jobs.append(str(job_id))
                    continue
                processed.append({
                    "job_item": job,
                    "score": hit_scores[i]
                })
            else:
                missing_jobs.append(str(job_id))
        
        if invalid_jobs:
            logger.warning(
                "postprocess_filtered_invalid_jobs",
                filtered_count=len(invalid_jobs),
                filtered_ids=invalid_jobs[:5]
            )
        
        if missing_jobs:
            logger.warning(
                "postprocess_missing_jobs",
                missing_count=len(missing_jobs),
                missing_ids=missing_jobs[:5]  # Log first 5 missing IDs
            )
        
        logger.info(
            "postprocess_completed",
            input_count=len(raw_results),
            output_count=len(processed),
            success_rate=f"{len(processed)/len(raw_results)*100:.1f}%" if raw_results else "0%"
        )
        
        return processed
