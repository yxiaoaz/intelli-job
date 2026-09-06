"""
统一数据库迁移脚本

整合所有 DDL 变更（含历史 commit），一次性执行：
  1. DROP 老表：session_intents, user_query_preferences（项目零用户，无需数据迁移）
  2. CREATE 所有当前注册的表（幂等，已存在则跳过）

覆盖范围：
  - memory-system-redesign: session_memories, user_memories
  - AI job explanation: job_ai_explanations
  - 以及所有已有表（users, resumes, jobs, ...）

用法：
    cd backend
    python scripts/migrate_all.py
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from app.models.base import Base

# noqa: import all ORM models so they register with Base.metadata
from app.models.user_memory import UserMemoryORM  # noqa: F401
from app.models.session_memory import SessionMemoryORM  # noqa: F401
from app.models import (  # noqa: F401
    User, Resume, ResumeAnalysis, JobBookmark,
    ChatSession, ChatMessage, JobItem, JobAIExplanation,
    JobSourceHealth, JobAtsRegistry,
)
from app.utils.logger import setup_logging, get_logger

load_dotenv()

# 老表（需要 drop，项目零用户无需数据迁移）
OLD_TABLES = ["session_intents", "user_query_preferences"]

# 幂等列迁移（job-source-adapter-refactor）：create_all 不会给已存在的表加列
IDEMPOTENT_COLUMNS = [
    "ALTER TABLE job_items ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ NULL",
    "ALTER TABLE job_items ADD COLUMN IF NOT EXISTS salary_min BIGINT NULL",
    "ALTER TABLE job_items ADD COLUMN IF NOT EXISTS salary_max BIGINT NULL",
]


def migrate():
    """执行迁移（同步）"""
    logger = get_logger()

    rds_drivername = os.getenv("RDS_DRIVERNAME", "postgresql+asyncpg")
    rds_username = os.getenv("RDS_USERNAME", "postgres")
    rds_password = os.getenv("RDS_PASSWORD", "password")
    rds_host = os.getenv("RDS_HOST", "localhost")
    rds_port = os.getenv("RDS_PORT", "5432")
    rds_db_name = os.getenv("RDS_DB_NAME", "intellijob")

    sync_drivername = rds_drivername.replace("postgresql+asyncpg", "postgresql+pg8000")
    database_url = f"{sync_drivername}://{rds_username}:{rds_password}@{rds_host}:{rds_port}/{rds_db_name}"

    logger.info(f"[DB] 数据库: {rds_host}:{rds_port}/{rds_db_name}")
    sync_engine = create_engine(database_url)

    try:
        with sync_engine.connect() as conn:
            # 1. Drop 老表
            for table in OLD_TABLES:
                logger.info(f"[DROP] DROP TABLE IF EXISTS {table}")
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            conn.commit()

        # 2. Create 所有当前注册的表（幂等）
        logger.info("[CREATE] 创建/检查所有表...")
        Base.metadata.create_all(bind=sync_engine)

        # 3. 幂等列迁移（已存在则跳过）
        with sync_engine.connect() as conn:
            for stmt in IDEMPOTENT_COLUMNS:
                logger.info(f"[ALTER] {stmt}")
                conn.execute(text(stmt))
            conn.commit()

        logger.info("[OK] 迁移完成！")
        logger.info("当前表列表:")
        for table in Base.metadata.tables.keys():
            logger.info(f"  - {table}")

    except Exception as e:
        logger.error(f"[FAIL] 迁移失败: {e}")
        raise
    finally:
        sync_engine.dispose()


if __name__ == "__main__":
    setup_logging()
    migrate()
