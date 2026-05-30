from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repositories.job_repo import JobRepository, BookmarkRepository
from app.services.job_matching_service import JobMatchingService
from app.schemas import JobMatchRequest, JobResponse
from app.api.dependencies import get_current_user
from app.models import User, JobBookmark
import uuid

router = APIRouter()


@router.post("/match", response_model=dict)
async def match_jobs(
    request: JobMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Match jobs based on user preferences and resume"""
    job_repo = JobRepository(db)
    bookmark_repo = BookmarkRepository(db)
    matching_service = JobMatchingService()
    
    try:
        # Perform job matching
        results = await matching_service.match_jobs(
            user_query_preference=request.user_query_preference,
            user_resume_profile=request.user_resume_profile,
            search_mode=request.search_mode,
            top_k=request.top_k,
            hard_filters=request.hard_filters,
            job_repo=job_repo
        )
        
        # Get user's bookmarks to check which jobs are bookmarked
        bookmarks = await bookmark_repo.get_user_bookmarks(current_user.id)
        bookmarked_job_ids = {b.job_id for b in bookmarks}
        
        # Format response
        formatted_results = []
        for item in results:
            job = item["job_item"]
            score = item["score"]
            
            formatted_results.append({
                "id": str(job.id),
                "company": job.company_name,
                "title": job.job_title,
                "recruitment_type": job.recruitment_type.value if job.recruitment_type else "未知",
                "location": job.location or "未知",
                "salary": job.salary or "NA",
                "education": job.min_academic_qualification.value if job.min_academic_qualification else "不限",
                "update_time": job.update_time.strftime("%Y-%m-%d") if job.update_time else None,
                "description": (job.description[:100] + "...") if job.description and len(job.description) > 100 else (job.description or "NA"),
                "full_description": job.description or "",
                "url": job.url or "",
                "score": score,
                "is_bookmarked": job.id in bookmarked_job_ids
            })
        
        return {
            "status": "success",
            "data": formatted_results,
            "count": len(formatted_results)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Job matching failed: {str(e)}"
        )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_detail(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific job"""
    job_repo = JobRepository(db)
    bookmark_repo = BookmarkRepository(db)
    
    job = await job_repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if bookmarked
    bookmark = await bookmark_repo.get_bookmark(current_user.id, job_id)
    
    return JobResponse(
        id=job.id,
        company=job.company_name or "未知",
        title=job.job_title or "未知",
        recruitment_type=job.recruitment_type.value if job.recruitment_type else "未知",
        location=job.location or "未知",
        salary=job.salary or "NA",
        education=job.min_academic_qualification.value if job.min_academic_qualification else "不限",
        update_time=job.update_time.strftime("%Y-%m-%d") if job.update_time else None,
        description=(job.description[:100] + "...") if job.description and len(job.description) > 100 else (job.description or "NA"),
        full_description=job.description or "",
        url=job.url or "",
        score=0.0,
        is_bookmarked=bookmark is not None
    )
