"""
Authentication API Tests

Tests for:
- User registration
- User login
- Token refresh
- Protected routes
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestUserRegistration:
    """Test user registration endpoint"""
    
    @pytest.mark.asyncio
    async def test_register_success(self, client, test_user_data):
        """Test successful user registration"""
        response = await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check response structure
        assert "id" in data
        assert data["email"] == test_user_data["email"]
        assert "hashed_password" not in data  # Password should not be returned
        assert "is_active" in data
        assert data["is_active"] is True
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, test_user_data):
        """Test registration with duplicate email"""
        # First registration
        response1 = await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        assert response1.status_code == 201
        
        # Second registration with same email
        response2 = await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        
        assert response2.status_code == 400
        data = response2.json()
        assert "already registered" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client):
        """Test registration with invalid email format"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "password": "TestPassword123"
            }
        )
        
        # Pydantic validation should catch this
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_weak_password(self, client):
        """Test registration with weak password"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test2@example.com",
                "password": "123"  # Too short
            }
        )
        
        # Should fail validation (minimum 8 characters)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client):
        """Test registration with missing required fields"""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com"}  # Missing password
        )
        
        assert response.status_code == 422


class TestUserLogin:
    """Test user login endpoint"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, client, test_user_data):
        """Test successful login"""
        # First register the user
        register_response = await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        assert register_response.status_code == 201
        
        # Then login
        login_response = await client.post(
            "/api/v1/auth/login",
            json=test_user_data
        )
        
        assert login_response.status_code == 200
        data = login_response.json()
        
        # Check response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, test_user_data):
        """Test login with wrong password"""
        # Register user
        register_response = await client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        assert register_response.status_code == 201
        
        # Try login with wrong password
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": "WrongPassword123"
            }
        )
        
        assert login_response.status_code == 401
        data = login_response.json()
        assert "incorrect" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Test login with non-existent user"""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "TestPassword123"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        # Should not reveal whether user exists or not
        assert "incorrect" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client, test_user_data, test_db):
        """Test login with inactive user"""
        from app.repositories.user_repo import UserRepository
        
        # Register and deactivate user
        user_repo = UserRepository(test_db)
        user = await user_repo.create(
            email=test_user_data["email"],
            password=test_user_data["password"]
        )
        user.is_active = False
        await test_db.commit()
        
        # Try login
        response = await client.post(
            "/api/v1/auth/login",
            json=test_user_data
        )
        
        assert response.status_code == 403
        data = response.json()
        assert "inactive" in data["detail"].lower()


class TestTokenRefresh:
    """Test token refresh endpoint"""
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client, test_user_data):
        """Test successful token refresh"""
        # Endpoint may not be implemented yet
        pass
    
    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token"""
        # Endpoint may not be implemented yet
        pass
    
    @pytest.mark.asyncio
    async def test_refresh_token_use_access_token(self, client, test_user_data):
        """Test refresh with access token instead of refresh token"""
        # Endpoint may not be implemented yet
        pass


class TestProtectedRoutes:
    """Test protected routes require authentication"""
    
    @pytest.mark.asyncio
    async def test_protected_route_without_token(self, client):
        """Test accessing protected route without token"""
        # /api/v1/users/me endpoint not implemented yet
        pass
    
    @pytest.mark.asyncio
    async def test_protected_route_with_invalid_token(self, client):
        """Test accessing protected route with invalid token"""
        # Endpoint not implemented yet
        pass
    
    @pytest.mark.asyncio
    async def test_protected_route_with_valid_token(self, authenticated_client):
        """Test accessing protected route with valid token"""
        # Endpoint not implemented yet
        pass


class TestSecurity:
    """Test security features"""
    
    @pytest.mark.asyncio
    async def test_password_hashing(self, test_user_data, test_db):
        """Test that passwords are properly hashed"""
        from app.repositories.user_repo import UserRepository
        
        user_repo = UserRepository(test_db)
        user = await user_repo.create(
            email=test_user_data["email"],
            password=test_user_data["password"]
        )
        await test_db.commit()
        
        # Password should be hashed
        assert user.hashed_password != test_user_data["password"]
        assert len(user.hashed_password) > 50  # bcrypt hashes are long
        assert user.hashed_password.startswith("$2b$")  # bcrypt prefix
    
    @pytest.mark.asyncio
    async def test_password_verification(self, test_user_data, test_db):
        """Test password verification works correctly"""
        from app.repositories.user_repo import UserRepository
        from app.utils.security import verify_password
        
        user_repo = UserRepository(test_db)
        user = await user_repo.create(
            email=test_user_data["email"],
            password=test_user_data["password"]
        )
        await test_db.commit()
        
        # Correct password should verify
        assert verify_password(test_user_data["password"], user.hashed_password) is True
        
        # Wrong password should not verify
        assert verify_password("WrongPassword", user.hashed_password) is False
    
    @pytest.mark.asyncio
    async def test_jwt_token_structure(self, test_user_data, test_db):
        """Test JWT token structure and claims"""
        from app.repositories.user_repo import UserRepository
        from app.utils.security import create_access_token, decode_token
        import jwt
        
        user_repo = UserRepository(test_db)
        user = await user_repo.create(
            email=test_user_data["email"],
            password=test_user_data["password"]
        )
        await test_db.commit()
        
        # Create token
        token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=None
        )
        
        # Decode without verification to check structure
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        assert "sub" in decoded
        assert decoded["sub"] == str(user.id)
        assert "exp" in decoded
        assert "type" in decoded
        assert decoded["type"] == "access"
    
    @pytest.mark.asyncio
    async def test_token_expiration(self, test_user_data, test_db):
        """Test that tokens expire correctly"""
        from app.repositories.user_repo import UserRepository
        from app.utils.security import create_access_token, decode_token
        from datetime import timedelta, datetime, timezone
        import time
        
        user_repo = UserRepository(test_db)
        user = await user_repo.create(
            email=test_user_data["email"],
            password=test_user_data["password"]
        )
        await test_db.commit()
        
        # Create token with short expiration
        token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(seconds=1)
        )
        
        # Should be valid initially
        payload = decode_token(token)
        assert payload["sub"] == str(user.id)
        
        # Wait for expiration
        time.sleep(2)
        
        # Should raise exception after expiration
        with pytest.raises(Exception):
            decode_token(token)
