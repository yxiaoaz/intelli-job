from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repositories.job_repo import JobRepository, BookmarkRepository
from app.services.job_matching_service import JobMatchingService
from app.services.query_enhancer import QueryEnhancer, extract_resume_profile
from app.schemas import JobMatchRequest, JobResponse, BookmarkResponse
from app.api.dependencies import get_current_user
from app.models import User, JobBookmark, Resume
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
        # --- Load user's active resume for personalized matching ---
        resume_profile = {}
        resume_result = await db.execute(
            select(Resume).where(
                Resume.user_id == current_user.id,
                Resume.active_status == True
            ).limit(1)
        )
        active_resume = resume_result.scalar_one_or_none()
        if active_resume and active_resume.extracted_content:
            resume_profile = extract_resume_profile(active_resume.extracted_content)
        
        # Merge resume profile into request if not already provided
        effective_resume_profile = request.user_resume_profile or {}
        if resume_profile and not effective_resume_profile:
            effective_resume_profile = resume_profile
        
        # --- LLM keyword enhancement ---
        enhancement_info = None
        keywords = (request.user_query_preference or {}).get("keywords", "")
        if keywords:
            enhancer = QueryEnhancer()
            enhancement_info = await enhancer.enhance(keywords, resume_profile or None)
            # Replace keywords with expanded version
            enhanced_query = enhancement_info["expanded_query"]
            effective_query_pref = {**(request.user_query_preference or {}), "keywords": enhanced_query}
        else:
            effective_query_pref = request.user_query_preference or {}
        
        # Perform job matching (skip internal enhancement since we already did it)
        results = await matching_service.match_jobs(
            user_query_preference=effective_query_pref,
            user_resume_profile=effective_resume_profile,
            search_mode=request.search_mode,
            top_k=request.top_k,
            hard_filters=request.hard_filters,
            job_repo=job_repo,
            skip_enhancement=True,
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
        
        response_data = {
            "status": "success",
            "data": formatted_results,
            "count": len(formatted_results)
        }
        
        # Include enhancement info for frontend display
        if enhancement_info and enhancement_info.get("synonyms"):
            response_data["enhancement"] = enhancement_info
        
        return response_data
    
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
        description=job.description or "NA",
        full_description=job.description or "",
        url=job.url or "",
        score=0.0,
        is_bookmarked=bookmark is not None
    )


@router.get("/bookmarks", response_model=list[BookmarkResponse])
async def get_bookmarks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all bookmarked jobs for current user"""
    bookmark_repo = BookmarkRepository(db)
    job_repo = JobRepository(db)
    
    bookmarks = await bookmark_repo.get_user_bookmarks(current_user.id)
    
    # Build response with job details
    result = []
    for bookmark in bookmarks:
        job = await job_repo.get_by_id(bookmark.job_id)
        if job:
            result.append(BookmarkResponse(
                id=bookmark.id,
                job_id=bookmark.job_id,
                status=bookmark.status.value if bookmark.status else "saved",
                notes=bookmark.notes,
                created_at=bookmark.created_at,
                job=JobResponse(
                    id=job.id,
                    company=job.company_name or "未知",
                    title=job.job_title or "未知",
                    recruitment_type=job.recruitment_type.value if job.recruitment_type else "未知",
                    location=job.location or "未知",
                    salary=job.salary or "NA",
                    education=job.min_academic_qualification.value if job.min_academic_qualification else "不限",
                    update_time=job.update_time.strftime("%Y-%m-%d") if job.update_time else None,
                    description=job.description or "NA",
                    full_description=job.description or "",
                    url=job.url or "",
                    score=0.0,
                    is_bookmarked=True
                )
            ))
    
    return result


@router.post("/bookmarks/{job_id}", response_model=BookmarkResponse, status_code=201)
async def create_bookmark(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Bookmark a job"""
    job_repo = JobRepository(db)
    bookmark_repo = BookmarkRepository(db)
    
    # Check if job exists
    job = await job_repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if already bookmarked
    existing = await bookmark_repo.get_bookmark(current_user.id, job_id)
    if existing:
        raise HTTPException(status_code=409, detail="Job already bookmarked")
    
    # Create bookmark
    bookmark = await bookmark_repo.create(current_user.id, job_id)
    await db.commit()
    await db.refresh(bookmark)
    
    return BookmarkResponse(
        id=bookmark.id,
        job_id=bookmark.job_id,
        status=bookmark.status.value if bookmark.status else "saved",
        notes=bookmark.notes,
        created_at=bookmark.created_at,
        job=JobResponse(
            id=job.id,
            company=job.company_name or "未知",
            title=job.job_title or "未知",
            recruitment_type=job.recruitment_type.value if job.recruitment_type else "未知",
            location=job.location or "未知",
            salary=job.salary or "NA",
            education=job.min_academic_qualification.value if job.min_academic_qualification else "不限",
            update_time=job.update_time.strftime("%Y-%m-%d") if job.update_time else None,
            description=job.description or "NA",
            full_description=job.description or "",
            url=job.url or "",
            score=0.0,
            is_bookmarked=True
        )
    )


@router.delete("/bookmarks/{job_id}", status_code=204)
async def delete_bookmark(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a bookmark"""
    bookmark_repo = BookmarkRepository(db)
    
    bookmark = await bookmark_repo.get_bookmark(current_user.id, job_id)
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    
    await bookmark_repo.delete(bookmark)
    await db.commit()
