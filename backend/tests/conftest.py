"""
Test configuration and fixtures
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.database import get_db


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


@pytest.fixture
def test_user_data():
    """Test user data"""
    return {
        "email": "test@example.com",
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
        email=test_user_data["email"],
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
