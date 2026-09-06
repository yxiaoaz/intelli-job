import uuid
import logging
from datetime import datetime
from typing import Union, List
from sqlalchemy import create_engine, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker, Session

from app.models import JobItem
from app.config import get_settings

logger = logging.getLogger(__name__)


class CrawlerDBController:
    """爬虫专用的数据库控制器，使用同步引擎"""
    
    def __init__(self):
        # 获取配置
        settings = get_settings()
        
        logger.info(f"Initializing CrawlerDBController - Database: {settings.DATABASE_URL}")
        
        # 从异步 URL 转换为同步 URL（统一使用 pg8000 驱动，纯 Python 无需编译）
        # 例如: postgresql+asyncpg:// -> postgresql+pg8000://
        sync_url = settings.DATABASE_URL.replace("+asyncpg", "+pg8000").replace("+aiosqlite", "")
        self.engine = create_engine(
            sync_url,
            echo=settings.DEBUG,
            pool_size=5,  # 降低连接池大小
            max_overflow=2,
            pool_timeout=10,  # 连接超时 10 秒
            pool_recycle=1800,
            connect_args={"timeout": 5},  # pg8000 连接超时参数为 timeout
        )
        self.session_maker = sessionmaker(bind=self.engine)
        logger.info("CrawlerDBController initialized successfully")
    
    @staticmethod
    def _job_values(job_item: JobItem) -> dict:
        """ORM 对象 → 核心插入所需的完整列值（含 fingerprint 与三新列）。"""
        return {
            "id": job_item.id,
            "source": job_item.source,
            "url": job_item.url,
            "fingerprint": job_item.fingerprint,
            "embedding_generated": job_item.embedding_generated or False,
            "job_title": job_item.job_title,
            "update_time": job_item.update_time,
            "location": job_item.location,
            "recruitment_type": job_item.recruitment_type,
            "min_academic_qualification": job_item.min_academic_qualification,
            "salary": job_item.salary,
            "published_at": job_item.published_at,
            "salary_min": job_item.salary_min,
            "salary_max": job_item.salary_max,
            "description": job_item.description,
            "company_name": job_item.company_name,
            "created_at": job_item.created_at or datetime.utcnow(),
            "updated_at": job_item.updated_at or datetime.utcnow(),
        }

    def insert_job_item(
        self, session: Session, job_item: Union[JobItem, List[JobItem]]
    ) -> List[uuid.UUID]:
        """插入职位数据；唯一约束冲突（url/fingerprint 及未来任意唯一约束）

        以不带推断目标的 ON CONFLICT DO NOTHING 静默跳过（design 决策 8），
        避免一条冲突回滚整批。返回实际插入的行 id 列表，调用方据此过滤
        embedding batch 与 Milvus 写入。
        """
        if isinstance(job_item, JobItem):
            job_item = [job_item]
        if not job_item:
            return []
        stmt = (
            pg_insert(JobItem)
            .values([self._job_values(j) for j in job_item])
            .on_conflict_do_nothing()
            .returning(JobItem.id)
        )
        result = session.execute(stmt)
        return [row[0] for row in result]

    def update_job_item_embedding_status_bulk(
        self, session: Session, job_item_ids: List[uuid.UUID], status: bool
    ):
        """批量更新职位 embedding 生成状态"""
        session.execute(
            update(JobItem),
            [
                {"id": job_item_id, "embedding_generated": status}
                for job_item_id in job_item_ids
            ],
        )
    
    def close(self):
        """关闭数据库引擎"""
        self.engine.dispose()
