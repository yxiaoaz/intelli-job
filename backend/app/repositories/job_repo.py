from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
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
        """Filter jobs by recruitment type, excluding incomplete records"""
        result = await self.session.execute(
            select(JobItem).where(
                and_(
                    JobItem.recruitment_type.in_(types),
                    JobItem.embedding_generated == True,
                    # 排除爬取失败的记录（岗位名称和公司名称都未知）
                    ~and_(
                        JobItem.job_title == "未知",
                        JobItem.company_name == "未知"
                    )
                )
            )
        )
        return result.scalars().all()
    
    async def filter_by_hard_conditions(
        self,
        recruitment_types: list[str] | None = None,
        min_education: str | None = None,
        update_time_after: str | None = None
    ) -> list[str]:
        """Apply multiple hard filters and return filtered job IDs as strings
        
        Args:
            recruitment_types: List of recruitment type strings (e.g., ["EXPERIENCED", "GRADUATE"])
            min_education: Minimum education level (e.g., "UNDERGRADUATE")
            update_time_after: ISO format datetime string (e.g., "2024-01-01T00:00:00")
            
        Returns:
            List of job IDs as strings that match all conditions
        """
        from datetime import datetime, timezone, timedelta
        
        conditions = [
            JobItem.embedding_generated == True,
            # 排除爬取失败的记录
            ~and_(
                JobItem.job_title == "未知",
                JobItem.company_name == "未知"
            )
        ]
        
        # 1. 招聘类型过滤
        if recruitment_types:
            # 将字符串转换为枚举值
            type_enums = [
                RecruitmentType[type_name] 
                for type_name in recruitment_types 
                if type_name in RecruitmentType.__members__
            ]
            if type_enums:
                conditions.append(JobItem.recruitment_type.in_(type_enums))
        
        # 2. 学历要求过滤
        if min_education:
            # 教育层级顺序：ALL < ASSOCIATE < UNDERGRADUATE < MASTERS < DOCTOR
            education_order = {
                'ALL': 0,
                'ASSOCIATE': 1,
                'UNDERGRADUATE': 2,
                'MASTERS': 3,
                'DOCTOR': 4
            }
            
            if min_education in education_order:
                min_level = education_order[min_education]
                # 获取所有 >= min_level 的教育级别
                valid_levels = [
                    edu for edu, level in education_order.items() 
                    if level >= min_level and edu != 'ALL'
                ]
                edu_enums = [
                    AcademicQualification[edu] 
                    for edu in valid_levels 
                    if edu in AcademicQualification.__members__
                ]
                if edu_enums:
                    conditions.append(JobItem.min_academic_qualification.in_(edu_enums))
        
        # 3. 更新时间过滤
        if update_time_after:
            try:
                dt = datetime.fromisoformat(update_time_after.replace('Z', '+00:00'))
                # UTC → 北京时间（与数据库存储时区一致），再去掉时区标记
                dt = dt.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
                conditions.append(JobItem.update_time >= dt)
            except (ValueError, AttributeError):
                # 如果日期格式错误，忽略此条件
                pass
        
        # 执行查询
        if len(conditions) == 2:  # 只有基础条件，没有额外过滤
            return []
        
        result = await self.session.execute(
            select(JobItem.id).where(and_(*conditions))
        )
        
        # 返回 UUID 字符串列表
        return [str(job_id) for (job_id,) in result.fetchall()]
    
    async def get_by_ids(self, job_ids: list[uuid.UUID]) -> list[JobItem]:
        """Get multiple jobs by IDs, excluding incomplete records"""
        if not job_ids:
            return []
        result = await self.session.execute(
            select(JobItem).where(
                and_(
                    JobItem.id.in_(job_ids),
                    # 排除爬取失败的记录（岗位名称和公司名称都未知）
                    ~and_(
                        JobItem.job_title == "未知",
                        JobItem.company_name == "未知"
                    )
                )
            )
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
