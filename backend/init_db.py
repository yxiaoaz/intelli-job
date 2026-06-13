"""
数据库初始化脚本
用于在 PostgreSQL 中创建所有表结构，以及初始化 Milvus/Zilliz 向量数据库
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from pymilvus import (
    MilvusClient,
    DataType,
    Function,
    FunctionType,
)
from app.models.base import Base
from app.models import User, Resume, ResumeAnalysis, UserQueryPreference, JobBookmark, ChatSession, ChatMessage, JobItem, SessionIntent
from app.utils.logger import setup_logging, get_logger

# 加载环境变量
load_dotenv()


async def init_db():
    """初始化 SQL 数据库，创建所有表"""
    logger = get_logger()
    
    # 从环境变量构建数据库 URL
    rds_drivername = os.getenv('RDS_DRIVERNAME', 'postgresql+asyncpg')
    rds_username = os.getenv('RDS_USERNAME', 'postgres')
    rds_password = os.getenv('RDS_PASSWORD', 'password')
    rds_host = os.getenv('RDS_HOST', 'localhost')
    rds_port = os.getenv('RDS_PORT', '5432')
    rds_db_name = os.getenv('RDS_DB_NAME', 'intellijob')
    
    # 将 asyncpg 改为 pg8000 用于同步连接（项目已安装）
    sync_drivername = rds_drivername.replace('postgresql+asyncpg', 'postgresql+pg8000')
    database_url = f"{sync_drivername}://{rds_username}:{rds_password}@{rds_host}:{rds_port}/{rds_db_name}"
    
    logger.info(f"🔗 数据库连接: {rds_host}:{rds_port}/{rds_db_name}")
    
    # 使用同步引擎
    sync_engine = create_engine(database_url)
    
    try:
        logger.info("开始初始化 SQL 数据库...")
        
        # 创建所有表
        Base.metadata.create_all(bind=sync_engine)
        
        logger.info("✅ SQL 数据库初始化成功！")
        logger.info("已创建的表:")
        for table in Base.metadata.tables.keys():
            logger.info(f"  - {table}")
            
    except Exception as e:
        logger.error(f"❌ SQL 数据库初始化失败: {e}")
        raise
    finally:
        sync_engine.dispose()


def init_vector_db(rewrite_if_exists: bool = False):
    """初始化 Milvus/Zilliz 向量数据库"""
    logger = get_logger()
    
    zilliz_uri = os.getenv("ZILLIZ_URI")
    zilliz_token = os.getenv("ZILLIZ_TOKEN")
    collection_name = os.getenv("ZILLIZ_JOB_ITEM_COLLECTION_NAME", "job_items")
    
    if not zilliz_uri or not zilliz_token:
        logger.warning("⚠️  ZILLIZ_URI 或 ZILLIZ_TOKEN 未配置，跳过向量数据库初始化")
        return
    
    logger.info("开始初始化向量数据库...")
    client = MilvusClient(uri=zilliz_uri, token=zilliz_token)
    
    # 检查 collection 是否已存在
    if client.has_collection(collection_name):
        logger.info(f"Collection '{collection_name}' 已存在")
        if rewrite_if_exists:
            logger.info("删除旧的 collection，重新创建...")
            client.drop_collection(collection_name)
        else:
            logger.info("继续使用现有的 collection，跳过创建")
            return
    
    # 创建 schema
    # id: UUID of length 36
    # content: job title and description, for hybrid search
    # sparse_vector: BM25 feature based on content
    # embedding: semantic embedding
    schema = MilvusClient.create_schema(
        auto_id=False,  # 手动管理 ID
        enable_dynamic_field=False,  # 不使用动态字段，保持 schema 严格
    )
    
    # 主键字段：职位 ID (UUID)
    schema.add_field(
        field_name="id",
        datatype=DataType.VARCHAR,
        is_primary=True,
        max_length=36,
        description="Job item UUID",
    )
    
    # 语言标识字段：用于 BM25 分析器选择
    schema.add_field(
        field_name="language",
        datatype=DataType.VARCHAR,
        max_length=5,
        description="Language code (en/cn)",
    )
    
    # 多语言分析器配置
    multi_analyzer_params = {
        "analyzers": {
            "english": {"type": "english"},  # English-optimized analyzer
            "chinese": {"type": "chinese"},  # Chinese-optimized analyzer
            "default": {"tokenizer": "icu"},  # Required fallback analyzer
        },
        "by_field": "language",  # Field determining analyzer selection
        "alias": {
            "cn": "chinese",  # Use "cn" as shorthand for Chinese
            "en": "english",  # Use "en" as shorthand for English
        },
    }
    
    # 内容字段：职位名称和描述（用于混合搜索）
    schema.add_field(
        field_name="content",
        datatype=DataType.VARCHAR,
        max_length=10000,  # 优化：从 60000 降低到 10000，足够存储职位信息
        multi_analyzer_params=multi_analyzer_params,
        enable_analyzer=True,  # Enable text analysis
        description="Job title and description for hybrid search",
    )
    
    # 稀疏向量字段：BM25 特征
    schema.add_field(
        field_name="sparse_vector",
        datatype=DataType.SPARSE_FLOAT_VECTOR,
        description="BM25 sparse vector for keyword search",
    )
    
    # 稠密向量字段：语义 embedding (1024 维)
    schema.add_field(
        field_name="embedding",
        datatype=DataType.FLOAT_VECTOR,
        dim=1024,  # Dimension for text-embedding-v4
        description="Semantic embedding vector",
    )
    
    # 配置 BM25 函数：自动从 content 生成 sparse_vector
    bm25_function = Function(
        name="bm25",
        function_type=FunctionType.BM25,
        input_field_names=["content"],
        output_field_names="sparse_vector",
    )
    schema.add_function(bm25_function)
    
    # 配置索引参数
    index_params = MilvusClient.prepare_index_params()
    
    # 稀疏向量索引：使用 SPARSE_INVERTED_INDEX + BM25
    index_params.add_index(
        field_name="sparse_vector",
        index_name="sparse_idx",  # 添加索引名称便于管理
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
    )
    
    # 稠密向量索引：使用 HNSW 替代 FLAT（更适合生产环境）
    # HNSW 提供更好的查询性能，同时保持较高的召回率
    index_params.add_index(
        field_name="embedding",
        index_name="dense_idx",  # 添加索引名称便于管理
        index_type="HNSW",  # 从 FLAT 改为 HNSW，提升查询性能
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},  # HNSW 参数
    )
    
    # 创建 collection
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
        consistency_level="Strong",  # 强一致性，确保数据立即可见
    )
    
    logger.info(f"✅ Collection '{collection_name}' 创建成功")
    logger.info(f"   - Schema: {len(schema.fields)} fields")
    logger.info(f"   - Functions: {len(schema.functions)} functions")
    logger.info(f"   - Indexes: sparse(BM25) + dense(HNSW)")
    logger.info(f"   - Consistency: Strong")


if __name__ == "__main__":
    setup_logging()
    logger = get_logger()
    
    logger.info("=" * 60)
    logger.info("Intelli-Job 数据库初始化")
    logger.info("=" * 60)
    
    # 初始化 SQL 数据库
    asyncio.run(init_db())
    
    # 初始化向量数据库
    init_vector_db(rewrite_if_exists=False)
    
    logger.info("=" * 60)
    logger.info("初始化完成！")
    logger.info("=" * 60)
