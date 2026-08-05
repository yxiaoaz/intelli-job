import asyncio
import json
import uuid
from typing import Any
from app.services.llm_service import LLMService
from app.services.vector_db_service import VectorDBService
from app.services.query_enhancer import QueryEnhancer
from app.repositories.job_repo import JobRepository
from app.models.constants import RecruitmentType
from app.utils.logger import get_logger

logger = get_logger()


class JobMatchingService:
    """Service for job matching using hybrid search"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.vector_db_service = VectorDBService()
        self._query_enhancer: QueryEnhancer | None = None
    
    @property
    def query_enhancer(self) -> QueryEnhancer:
        """延迟初始化 QueryEnhancer，避免 skip_enhancement=True 时白创建 ChatOpenAI 实例"""
        if self._query_enhancer is None:
            self._query_enhancer = QueryEnhancer()
        return self._query_enhancer
    
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
            skip_enhancement: If True, skip LLM keyword enhancement
                (set True when called from Chat Agent which already does intent understanding)
            
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
        
        # Step 1: Apply hard filters
        filtered_job_ids = await self._apply_hard_filters(hard_filters, job_repo)
        filter_expr = f"id IN {filtered_job_ids}" if filtered_job_ids else ""
        
        # Step 1.5: LLM keyword enhancement (optional)
        if not skip_enhancement and user_query_preference.get("keywords"):
            keywords = user_query_preference["keywords"]
            enhanced = await self.query_enhancer.enhance(keywords, user_resume_profile or None)
            # Replace keywords with expanded version
            user_query_preference = {**user_query_preference, "keywords": enhanced["expanded_query"]}
            logger.info(
                "query_enhanced_in_matching",
                original=keywords,
                expanded=enhanced["expanded_query"][:100]
            )
        
        # Step 2: Format user input
        user_input_str = self._format_user_input(user_query_preference, user_resume_profile)
        
        logger.info(
            "user_input_formatted",
            search_mode=search_mode,
            input_length=len(user_input_str),
            input_preview=user_input_str[:200]
        )
        
        # Step 3: Perform search based on mode
        # Normalize search mode: "keyword"/"vector" -> "sparse"/"semantic"
        normalized_mode = search_mode.lower()
        if normalized_mode in ["keyword", "fulltext"]:
            normalized_mode = "sparse"
        elif normalized_mode == "vector":  # ✅ 添加 vector 别名支持
            normalized_mode = "semantic"
        
        if normalized_mode == "semantic":
            logger.info("starting_semantic_search")
            user_embedding = await self.llm_service.generate_embedding(user_input_str)
            results = await asyncio.to_thread(
                self.vector_db_service.search_semantic,
                embedding=user_embedding,
                top_k=top_k,
                filter_expr=filter_expr
            )
            logger.info(
                "semantic_search_completed",
                result_count=len(results) if results else 0
            )
        elif normalized_mode == "sparse":
            logger.info("starting_sparse_search")
            results = await asyncio.to_thread(
                self.vector_db_service.search_sparse,
                text=user_input_str,
                top_k=top_k,
                filter_expr=filter_expr
            )
            logger.info(
                "sparse_search_completed",
                result_count=len(results) if results else 0
            )
        elif normalized_mode == "hybrid":
            logger.info("starting_hybrid_search")
            user_embedding = await self.llm_service.generate_embedding(user_input_str)
            results = await asyncio.to_thread(
                self.vector_db_service.search_hybrid,
                embedding=user_embedding,
                text=user_input_str,
                top_k=top_k,
                filter_expr=filter_expr
            )
            logger.info(
                "hybrid_search_completed",
                result_count=len(results) if results else 0
            )
        else:
            raise ValueError(f"Unsupported search mode: {search_mode}. Supported modes: semantic, sparse/keyword/fulltext, hybrid")
        
        # Step 4: Post-process results
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
    
    @staticmethod
    def build_semantic_query_from_intent(
        intent: dict,
        user_message: str,
        include_resume: bool = True
    ) -> dict:
        """
        从 Intent 构建分层 Query，平衡精准度和召回率
        
        Args:
            intent: Intent 字典（从 Markdown 文件加载或 Agent 构造）
            user_message: 用户当前消息
            include_resume: 是否包含简历信息
            
        Returns:
            {
                "semantic_query": "...",  # 用于向量搜索
                "hard_filters": {...},     # 用于硬过滤
            }
        """
        # === 第1层：核心语义（必须包含）===
        semantic_parts = []
        
        # 1.1 用户当前消息（最高优先级）
        if user_message:
            semantic_parts.append(user_message)
        
        # 1.2 目标岗位（从 intent 提取）
        if intent.get("preferred_job_titles"):
            direction = intent.get("search_direction") or intent["preferred_job_titles"][0]
            semantic_parts.append(f"岗位：{direction}")
        
        # 1.3 关键技能（从简历或 intent 提取）
        skills = intent.get("skills") or []
        if skills:
            # 只取前5个核心技能，避免噪声
            semantic_parts.append(f"技能：{', '.join(skills[:5])}")
        
        # === 第2层：硬过滤（不参与向量搜索，但用于后过滤）===
        hard_filters = {}
        
        # 2.1 城市（如果有明确意向）
        if intent.get("preferred_city"):
            hard_filters["location"] = intent["preferred_city"]
        
        # 2.2 薪资范围（如果用户明确提及）
        if intent.get("salary_expectation"):
            salary = intent["salary_expectation"]
            if isinstance(salary, dict):
                hard_filters["salary_min"] = salary.get("min")
                hard_filters["salary_max"] = salary.get("max")
            elif hasattr(salary, 'min'):  # Pydantic 对象
                hard_filters["salary_min"] = salary.min
                hard_filters["salary_max"] = salary.max
        
        return {
            "semantic_query": " ".join(semantic_parts),
            "hard_filters": hard_filters,
        }
