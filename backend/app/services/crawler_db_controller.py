import uuid
import logging
from typing import Union, List
from sqlalchemy import create_engine, insert, update
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
    
    def insert_job_item(
        self, session: Session, job_item: Union[JobItem, List[JobItem]]
    ):
        """插入职位数据到数据库"""
        if (
            isinstance(job_item, List)
            and len(job_item) > 0
            and all([isinstance(j, JobItem) for j in job_item])
        ):
            if len(job_item) > 10:
                # 批量插入
                session.execute(insert(JobItem), [j.to_dict() for j in job_item])
            else:
                session.add_all(job_item)
        elif isinstance(job_item, JobItem):
            session.add(job_item)

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
