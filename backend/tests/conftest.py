"""
Test configuration and fixtures
"""
import os

# 限流阈值在 app.core.rate_limiter 模块 import 时固化，必须在导入 app 前放开，
# 否则测试套内多个 auth/接口请求会触发分档限流（429）污染存量测试。
# 限流行为本身由 tests/test_rate_limiter.py 用独立 Limiter 实例专项验证。
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")
os.environ.setdefault("RATE_LIMIT_AUTH_PER_MINUTE", "100000")
os.environ.setdefault("RATE_LIMIT_AI_PER_MINUTE", "100000")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.database import get_db


# ✅ SQLite 内存库不支持 PostgreSQL 的 JSONB 类型，
# 注册方言级渲染规则使其退化为普通 JSON，避免建表失败
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(type_, compiler, **kw):
    return "JSON"


# Test database URL (in-memory SQLite for fast testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine):
    """Create test database session"""
    async_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
        await session.close()


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    """Create test HTTP client"""
    # Override the database dependency
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    # Clean up overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def fake_redis(monkeypatch):
    """fakeredis 替换 app.core.redis 单例，单测不得直连 .env 的 Redis Cloud 实例"""
    import fakeredis.aioredis
    from app.core import redis as redis_module

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_module, "_redis", fake)
    yield fake
    await fake.flushall()
    await fake.aclose()


@pytest.fixture
def broken_redis(monkeypatch):
    """模拟 Redis 不可用：所有操作抛 ConnectionError（验证 safe_redis 降级放行）"""
    from app.core import redis as redis_module

    class _BrokenRedis:
        def __getattr__(self, name):
            raise ConnectionError("redis down")

    monkeypatch.setattr(redis_module, "_redis", _BrokenRedis())


@pytest.fixture
def test_user_data():
    """Test user data"""
    return {
        "username": "testuser",
        "password": "TestPassword123"
    }


@pytest_asyncio.fixture
async def authenticated_client(client, test_user_data, test_db):
    """Create an authenticated test client"""
    from app.repositories.user_repo import UserRepository
    from app.utils.security import create_access_token
    
    # Create test user
    user_repo = UserRepository(test_db)
    user = await user_repo.create(
        username=test_user_data["username"],
        password=test_user_data["password"]
    )
    await test_db.commit()
    
    # Generate access token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=None
    )
    
    # Add authorization header
    client.headers["Authorization"] = f"Bearer {access_token}"
    
    yield client
    
    # Clean up
    client.headers.pop("Authorization", None)
