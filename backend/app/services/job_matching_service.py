import json
import uuid
from typing import Any
from app.services.llm_service import LLMService
from app.services.vector_db_service import VectorDBService
from app.repositories.job_repo import JobRepository
from app.models.constants import RecruitmentType
from app.utils.logger import get_logger

logger = get_logger()


class JobMatchingService:
    """Service for job matching using hybrid search"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.vector_db_service = VectorDBService()
    
    async def match_jobs(
        self,
        user_query_preference: dict[str, Any],
        user_resume_profile: dict[str, Any],
        search_mode: str = "hybrid",
        top_k: int = 100,
        hard_filters: dict[str, Any] = {},
        job_repo: JobRepository = None
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
            
        Returns:
            List of matched jobs with scores
        """
        logger.info(
            "job_matching_started",
            search_mode=search_mode,
            top_k=top_k,
            has_filters=len(hard_filters) > 0
        )
        
        # Step 1: Apply hard filters
        filtered_job_ids = await self._apply_hard_filters(hard_filters, job_repo)
        filter_expr = f"id IN {filtered_job_ids}" if filtered_job_ids else ""
        
        # Step 2: Format user input
        user_input_str = self._format_user_input(user_query_preference, user_resume_profile)
        
        # Step 3: Perform search based on mode
        if search_mode == "semantic":
            user_embedding = self.llm_service.generate_embedding(user_input_str)
            results = self.vector_db_service.search_semantic(
                embedding=user_embedding,
                top_k=top_k,
                filter_expr=filter_expr
            )
        elif search_mode == "sparse":
            results = self.vector_db_service.search_sparse(
                text=user_input_str,
                top_k=top_k,
                filter_expr=filter_expr
            )
        elif search_mode == "hybrid":
            user_embedding = self.llm_service.generate_embedding(user_input_str)
            results = self.vector_db_service.search_hybrid(
                embedding=user_embedding,
                text=user_input_str,
                top_k=top_k,
                filter_expr=filter_expr
            )
        else:
            raise ValueError(f"Unsupported search mode: {search_mode}")
        
        # Step 4: Post-process results
        processed_results = await self._postprocess_results(results, job_repo)
        
        logger.info("job_matching_completed", result_count=len(processed_results))
        return processed_results
    
    async def _apply_hard_filters(
        self, 
        hard_filters: dict[str, Any],
        job_repo: JobRepository
    ) -> list[str]:
        """Apply hard filters and return filtered job IDs"""
        if not job_repo or 'recruitment_type' not in hard_filters:
            return []
        
        recruitment_types = [
            RecruitmentType[type_name] 
            for type_name in hard_filters.get('recruitment_type', [])
        ]
        
        if not recruitment_types:
            return []
        
        filtered_jobs = await job_repo.filter_by_recruitment_type(recruitment_types)
        return [str(job.id) for job in filtered_jobs]
    
    def _format_user_input(
        self,
        user_query_preference: dict[str, Any],
        user_resume_profile: dict[str, Any]
    ) -> str:
        """Format user input for sparse search"""
        res_dict = {
            "求职意愿 (job intention)": {
                "描述": "用户的求职偏好",
                "内容": user_query_preference
            },
            "简历信息 (resume information)": {
                "描述": "用户的技能和背景",
                "内容": user_resume_profile
            }
        }
        return json.dumps(res_dict, ensure_ascii=False, indent=2)
    
    async def _postprocess_results(
        self,
        raw_results: list[dict],
        job_repo: JobRepository
    ) -> list[dict]:
        """Post-process search results"""
        if not raw_results:
            return []
        
        hit_ids = [uuid.UUID(result["id"]) for result in raw_results]
        hit_scores = [result["distance"] for result in raw_results]
        
        # Fetch job details from database
        if job_repo:
            jobs = await job_repo.get_by_ids(hit_ids)
            job_map = {job.id: job for job in jobs}
        else:
            job_map = {}
        
        # Build response
        processed = []
        for i, job_id in enumerate(hit_ids):
            job = job_map.get(job_id)
            if job:
                processed.append({
                    "job_item": job,
                    "score": hit_scores[i]
                })
        
        return processed
