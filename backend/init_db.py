"""
数据库初始化脚本
用于在 PostgreSQL 中创建所有表结构
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from app.models.base import Base
from app.models import User, Resume, UserQueryPreference, JobBookmark, ChatSession, ChatMessage, JobItem
from app.utils.logger import setup_logging, get_logger

# 加载环境变量
load_dotenv()


async def init_db():
    """初始化数据库，创建所有表"""
    logger = get_logger()
    
    # 从环境变量构建数据库 URL
    rds_drivername = os.getenv('RDS_DRIVERNAME', 'postgresql+asyncpg')
    rds_username = os.getenv('RDS_USERNAME', 'postgres')
    rds_password = os.getenv('RDS_PASSWORD', 'password')
    rds_host = os.getenv('RDS_HOST', 'localhost')
    rds_port = os.getenv('RDS_PORT', '5432')
    rds_db_name = os.getenv('RDS_DB_NAME', 'intellijob')
    
    # 将 asyncpg 改为 psycopg2 用于同步连接
    sync_drivername = rds_drivername.replace('postgresql+asyncpg', 'postgresql').replace('postgresql+pg8000', 'postgresql')
    database_url = f"{sync_drivername}://{rds_username}:{rds_password}@{rds_host}:{rds_port}/{rds_db_name}"
    
    logger.info(f"🔗 数据库连接: {rds_host}:{rds_port}/{rds_db_name}")
    
    # 使用同步引擎
    sync_engine = create_engine(database_url)
    
    try:
        logger.info("开始初始化数据库...")
        
        # 创建所有表
        Base.metadata.create_all(bind=sync_engine)
        
        logger.info("✅ 数据库初始化成功！")
        logger.info("已创建的表:")
        for table in Base.metadata.tables.keys():
            logger.info(f"  - {table}")
            
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        raise
    finally:
        sync_engine.dispose()


if __name__ == "__main__":
    setup_logging()
    logger = get_logger()
    
    logger.info("=" * 60)
    logger.info("Intelli-Job 数据库初始化")
    logger.info("=" * 60)
    
    asyncio.run(init_db())
    
    logger.info("=" * 60)
    logger.info("初始化完成！")
    logger.info("=" * 60)
