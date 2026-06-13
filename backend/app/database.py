from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,  # ✅ 连接回收时间（秒），避免 stale connections
    pool_pre_ping=True,  # ✅ 使用前检查连接是否有效
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """Dependency for getting database session
    
    ✅ 修复热重载时的连接问题：
    - 不使用 async with，避免上下文管理器在 reload 时异常
    - 手动管理 session 生命周期
    - pool_pre_ping=True 自动检查连接有效性
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database session error: {type(e).__name__}: {e}")
        raise
    finally:
        await session.close()
