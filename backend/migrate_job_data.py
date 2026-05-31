"""
数据迁移脚本：从旧的 job_item_db 表迁移到新的 job_items 表
"""
import asyncio
import hashlib
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.utils.logger import setup_logging, get_logger

# 加载环境变量
load_dotenv()


def generate_fingerprint(url: str, job_title: str, company_name: str) -> str:
    """
    生成职位去重指纹
    基于 URL、职位标题和公司名称生成唯一标识
    """
    content = f"{url}|{job_title}|{company_name}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()


async def migrate_data():
    """执行数据迁移"""
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
    
    # 使用同步引擎进行迁移（更简单）
    sync_engine = create_engine(database_url)
    
    try:
        with Session(sync_engine) as session:
            logger.info("=" * 60)
            logger.info("开始数据迁移：job_item_db → job_items")
            logger.info("筛选条件：update_time 在最近30天内")
            logger.info("=" * 60)
            
            # 1. 检查源表是否存在
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'job_item_db'
                );
            """))
            source_exists = result.scalar()
            
            if not source_exists:
                logger.error("❌ 源表 job_item_db 不存在！")
                return
            
            logger.info("✅ 源表 job_item_db 存在")
            
            # 2. 检查目标表是否存在
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'job_items'
                );
            """))
            target_exists = result.scalar()
            
            if not target_exists:
                logger.error("❌ 目标表 job_items 不存在！请先运行 init_db.py 初始化数据库")
                return
            
            logger.info("✅ 目标表 job_items 存在")
            
            # 3. 获取源表数据量
            result = session.execute(text("SELECT COUNT(*) FROM job_item_db"))
            total_count = result.scalar()
            logger.info(f"📊 源表中共有 {total_count} 条记录")
            
            if total_count == 0:
                logger.info("⚠️ 源表为空，无需迁移")
                return
            
            # 4. 获取目标表已有数据量
            result = session.execute(text("SELECT COUNT(*) FROM job_items"))
            existing_count = result.scalar()
            logger.info(f"📊 目标表中已有 {existing_count} 条记录")
            
            # 5. 查询最近一个月的数据
            result = session.execute(text("""
                SELECT id, source, url, embedding_generated, job_title, 
                       update_time, location, recruitment_type, 
                       min_academic_qualification, salary, description, 
                       company_name
                FROM job_item_db
                WHERE update_time >= NOW() - INTERVAL '30 days'
                   OR update_time IS NULL
                ORDER BY update_time DESC NULLS LAST
            """))
            
            old_records = result.fetchall()
            logger.info(f"📋 读取到 {len(old_records)} 条待迁移记录（最近30天内）")
            
            if len(old_records) == 0:
                logger.info("⚠️ 没有符合条件的记录，无需迁移")
                return
            
            # 6. 迁移数据
            migrated_count = 0
            skipped_count = 0
            error_count = 0
            
            for idx, record in enumerate(old_records, 1):
                try:
                    # 解析记录
                    old_id = record[0]
                    source = record[1]
                    url = record[2]
                    embedding_generated = record[3]
                    job_title = record[4]
                    update_time = record[5]
                    location = record[6]
                    recruitment_type = record[7]
                    min_academic_qualification = record[8]
                    salary = record[9]
                    description = record[10]
                    company_name = record[11]
                    
                    # 生成指纹
                    fingerprint = generate_fingerprint(
                        url or "", 
                        job_title or "", 
                        company_name or ""
                    )
                    
                    # 检查是否已存在（通过 URL 或 fingerprint）
                    check_result = session.execute(text("""
                        SELECT id FROM job_items 
                        WHERE url = :url OR fingerprint = :fingerprint
                    """), {"url": url, "fingerprint": fingerprint})
                    
                    if check_result.fetchone():
                        skipped_count += 1
                        if idx % 100 == 0:
                            logger.info(f"处理进度: {idx}/{len(old_records)} (跳过: {skipped_count})")
                        continue
                    
                    # 插入新记录
                    now = datetime.utcnow()
                    session.execute(text("""
                        INSERT INTO job_items (
                            id, source, url, fingerprint, embedding_generated,
                            job_title, update_time, location, recruitment_type,
                            min_academic_qualification, salary, description,
                            company_name, created_at, updated_at
                        ) VALUES (
                            :id, :source, :url, :fingerprint, :embedding_generated,
                            :job_title, :update_time, :location, :recruitment_type,
                            :min_academic_qualification, :salary, :description,
                            :company_name, :created_at, :updated_at
                        )
                    """), {
                        "id": old_id,
                        "source": source,
                        "url": url,
                        "fingerprint": fingerprint,
                        "embedding_generated": embedding_generated or False,
                        "job_title": job_title,
                        "update_time": update_time,
                        "location": location,
                        "recruitment_type": recruitment_type,
                        "min_academic_qualification": min_academic_qualification,
                        "salary": salary or "NA",
                        "description": description,
                        "company_name": company_name,
                        "created_at": now,
                        "updated_at": now,
                    })
                    
                    migrated_count += 1
                    
                    # 每 100 条提交一次
                    if migrated_count % 100 == 0:
                        session.commit()
                        logger.info(f"✅ 已迁移 {migrated_count} 条记录...")
                    
                    if idx % 100 == 0:
                        logger.info(f"处理进度: {idx}/{len(old_records)}")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ 迁移第 {idx} 条记录时出错: {e}")
                    session.rollback()
            
            # 最后提交剩余数据
            session.commit()
            
            # 7. 输出迁移结果
            logger.info("=" * 60)
            logger.info("🎉 数据迁移完成！")
            logger.info("=" * 60)
            logger.info(f"📊 迁移统计:")
            logger.info(f"   - 源表总记录数: {total_count}")
            logger.info(f"   - 成功迁移: {migrated_count}")
            logger.info(f"   - 跳过重复: {skipped_count}")
            logger.info(f"   - 迁移失败: {error_count}")
            logger.info(f"   - 目标表现有: {existing_count + migrated_count}")
            logger.info("=" * 60)
            
    except Exception as e:
        logger.error(f"❌ 迁移过程中发生错误: {e}")
        raise
    finally:
        sync_engine.dispose()


if __name__ == "__main__":
    setup_logging()
    logger = get_logger()
    
    logger.info("=" * 60)
    logger.info("Intelli-Job 数据迁移工具")
    logger.info("从 job_item_db 迁移到 job_items")
    logger.info("=" * 60)
    
    asyncio.run(migrate_data())
    
    logger.info("=" * 60)
    logger.info("迁移程序结束")
    logger.info("=" * 60)
