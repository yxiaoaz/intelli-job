"""
添加 LangGraph Checkpointer 表的迁移脚本
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from app.utils.logger import setup_logging, get_logger

load_dotenv()


async def add_checkpointer_table():
    """添加 langgraph_checkpoints 表"""
    logger = get_logger()
    
    # 构建数据库 URL
    rds_drivername = os.getenv('RDS_DRIVERNAME', 'postgresql+asyncpg')
    rds_username = os.getenv('RDS_USERNAME', 'postgres')
    rds_password = os.getenv('RDS_PASSWORD', 'password')
    rds_host = os.getenv('RDS_HOST', 'localhost')
    rds_port = os.getenv('RDS_PORT', '5432')
    rds_db_name = os.getenv('RDS_DB_NAME', 'intellijob')
    
    sync_drivername = rds_drivername.replace('postgresql+asyncpg', 'postgresql').replace('postgresql+pg8000', 'postgresql')
    database_url = f"{sync_drivername}://{rds_username}:{rds_password}@{rds_host}:{rds_port}/{rds_db_name}"
    
    sync_engine = create_engine(database_url)
    
    try:
        logger.info("开始创建 langgraph_checkpoints 表...")
        
        with sync_engine.connect() as conn:
            # 创建 checkpoints 表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    thread_id VARCHAR(255) NOT NULL,
                    checkpoint JSONB NOT NULL,
                    metadata JSONB,
                    parent_checkpoint VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(thread_id)
                );
            """))
            
            # 创建索引
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id 
                ON langgraph_checkpoints(thread_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at 
                ON langgraph_checkpoints(created_at DESC);
            """))
            
            conn.commit()
        
        logger.info("✅ langgraph_checkpoints 表创建成功！")
        
    except Exception as e:
        logger.error(f"❌ 创建表失败: {e}")
        raise
    finally:
        sync_engine.dispose()


if __name__ == "__main__":
    setup_logging()
    logger = get_logger()
    
    logger.info("=" * 60)
    logger.info("添加 LangGraph Checkpointer 表")
    logger.info("=" * 60)
    
    asyncio.run(add_checkpointer_table())
    
    logger.info("=" * 60)
    logger.info("完成！")
    logger.info("=" * 60)
