from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models import JobItem, JobBookmark
from app.models.constants import RecruitmentType, ApplicationStatus
import uuid


class JobRepository:
    """Repository for Job operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, job_id: uuid.UUID) -> JobItem | None:
        """Get job by ID"""
        result = await self.session.execute(
            select(JobItem).where(JobItem.id == job_id)
        )
        return result.scalar_one_or_none()
    
    async def filter_by_recruitment_type(
        self, 
        types: list[RecruitmentType]
    ) -> list[JobItem]:
        """Filter jobs by recruitment type"""
        result = await self.session.execute(
            select(JobItem).where(
                and_(
                    JobItem.recruitment_type.in_(types),
                    JobItem.embedding_generated == True
                )
            )
        )
        return result.scalars().all()
    
    async def get_by_ids(self, job_ids: list[uuid.UUID]) -> list[JobItem]:
        """Get multiple jobs by IDs"""
        if not job_ids:
            return []
        result = await self.session.execute(
            select(JobItem).where(JobItem.id.in_(job_ids))
        )
        return result.scalars().all()
    
    async def bulk_insert(self, jobs: list[JobItem]) -> None:
        """Bulk insert jobs"""
        self.session.add_all(jobs)
        await self.session.flush()


class BookmarkRepository:
    """Repository for Bookmark operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_user_bookmarks(self, user_id: uuid.UUID) -> list[JobBookmark]:
        """Get all bookmarks for a user"""
        result = await self.session.execute(
            select(JobBookmark)
            .where(JobBookmark.user_id == user_id)
            .order_by(JobBookmark.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_bookmark(self, user_id: uuid.UUID, job_id: uuid.UUID) -> JobBookmark | None:
        """Get specific bookmark"""
        result = await self.session.execute(
            select(JobBookmark).where(
                and_(
                    JobBookmark.user_id == user_id,
                    JobBookmark.job_id == job_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def create(self, user_id: uuid.UUID, job_id: uuid.UUID) -> JobBookmark:
        """Create a bookmark"""
        bookmark = JobBookmark(user_id=user_id, job_id=job_id)
        self.session.add(bookmark)
        await self.session.flush()
        return bookmark
    
    async def update_status(
        self, 
        bookmark: JobBookmark, 
        status: ApplicationStatus,
        notes: str | None = None
    ) -> JobBookmark:
        """Update bookmark status"""
        bookmark.status = status
        if notes is not None:
            bookmark.notes = notes
        await self.session.flush()
        return bookmark
    
    async def delete(self, bookmark: JobBookmark) -> None:
        """Delete a bookmark"""
        await self.session.delete(bookmark)
