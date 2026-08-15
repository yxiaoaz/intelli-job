"""
[DEPRECATED] 已整合到 scripts/migrate_all.py，请使用新脚本。

memory-system-redesign 迁移脚本

项目当前零用户，无需数据迁移。
本脚本仅做 DDL 变更：
  1. DROP 老表：session_intents, user_query_preferences
  2. CREATE 新表：session_memories, user_memories

用法：
    cd backend
    python scripts/migrate_memory_redesign.py
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from app.models.base import Base
# noqa: import new ORM so they register with Base.metadata
from app.models.user_memory import UserMemoryORM  # noqa: F401
from app.models.session_memory import SessionMemoryORM  # noqa: F401
from app.models import (  # noqa: F401
    User, Resume, ResumeAnalysis, JobBookmark,
    ChatSession, ChatMessage, JobItem,
)
from app.utils.logger import setup_logging, get_logger

load_dotenv()

# 老表（需要 drop）
OLD_TABLES = ["session_intents", "user_query_preferences"]


async def migrate():
    """执行迁移"""
    logger = get_logger()

    rds_drivername = os.getenv("RDS_DRIVERNAME", "postgresql+asyncpg")
    rds_username = os.getenv("RDS_USERNAME", "postgres")
    rds_password = os.getenv("RDS_PASSWORD", "password")
    rds_host = os.getenv("RDS_HOST", "localhost")
    rds_port = os.getenv("RDS_PORT", "5432")
    rds_db_name = os.getenv("RDS_DB_NAME", "intellijob")

    sync_drivername = rds_drivername.replace("postgresql+asyncpg", "postgresql+pg8000")
    database_url = f"{sync_drivername}://{rds_username}:{rds_password}@{rds_host}:{rds_port}/{rds_db_name}"

    logger.info(f"🔗 数据库: {rds_host}:{rds_port}/{rds_db_name}")
    sync_engine = create_engine(database_url)

    try:
        with sync_engine.connect() as conn:
            # 1. Drop 老表
            for table in OLD_TABLES:
                logger.info(f"🗑️  DROP TABLE IF EXISTS {table}")
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            conn.commit()

        # 2. Create 新表（Base.metadata 已包含所有当前 ORM）
        logger.info("🔨 创建新表...")
        Base.metadata.create_all(bind=sync_engine)

        logger.info("✅ 迁移完成！")
        logger.info("当前表列表:")
        for table in Base.metadata.tables.keys():
            logger.info(f"  - {table}")

    except Exception as e:
        logger.error(f"❌ 迁移失败: {e}")
        raise
    finally:
        sync_engine.dispose()


if __name__ == "__main__":
    setup_logging()
    asyncio.run(migrate())
