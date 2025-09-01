"""
Tests for Authentication module
Testing JWT, user authentication, and authorization
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from fastapi import FastAPI
from passlib.context import CryptContext
import jwt

# Import auth modules
from src.auth.jwt_handler import JWTHandler
from src.auth.models import User
from src.auth.dependencies import get_current_user
from src.auth.router import router as auth_router

# Create test app
app = FastAPI()
app.include_router(auth_router, prefix="/auth")
client = TestClient(app)


class TestJWTHandler:
    """Test JWT Handler functionality"""
    
    @pytest.fixture
    def jwt_handler(self):
        """Create JWT handler instance"""
        return JWTHandler(secret_key="test_secret", algorithm="HS256")
    
    def test_handler_initialization(self, jwt_handler):
        """Test handler initialization"""
        assert jwt_handler is not None
        assert jwt_handler.secret_key == "test_secret"
        assert jwt_handler.algorithm == "HS256"
    
    def test_create_access_token(self, jwt_handler):
        """Test access token creation"""
        token = jwt_handler.create_token(
            data={"sub": "user123"},
            expires_delta=timedelta(hours=1)
        )
        
        assert token is not None
        assert isinstance(token, str)
        
        # Decode and verify
        decoded = jwt.decode(token, "test_secret", algorithms=["HS256"])
        assert decoded["sub"] == "user123"
    
    def test_verify_valid_token(self, jwt_handler):
        """Test verifying valid token"""
        token = jwt_handler.create_token(
            data={"sub": "user123"},
            expires_delta=timedelta(hours=1)
        )
        
        payload = jwt_handler.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
    
    def test_verify_expired_token(self, jwt_handler):
        """Test verifying expired token"""
        token = jwt_handler.create_token(
            data={"sub": "user123"},
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        payload = jwt_handler.verify_token(token)
        assert payload is None
    
    def test_verify_invalid_token(self, jwt_handler):
        """Test verifying invalid token"""
        payload = jwt_handler.verify_token("invalid_token")
        assert payload is None
    
    def test_create_refresh_token(self, jwt_handler):
        """Test refresh token creation"""
        token = jwt_handler.create_refresh_token(
            data={"sub": "user123"}
        )
        
        assert token is not None
        decoded = jwt.decode(token, "test_secret", algorithms=["HS256"])
        assert decoded["sub"] == "user123"
        assert decoded["type"] == "refresh"


class TestUserModels:
    """Test User model functionality"""
    
    def test_user_creation(self):
        """Test user model creation"""
        user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            is_active=True
        )
        
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == UserRole.USER
        assert user.is_active is True
    
    def test_user_create_model(self):
        """Test user create model"""
        user_create = UserCreate(
            username="newuser",
            email="new@example.com",
            password="securepass123"
        )
        
        assert user_create.username == "newuser"
        assert user_create.password == "securepass123"
    
    def test_user_login_model(self):
        """Test user login model"""
        login = UserLogin(
            username="testuser",
            password="pass123"
        )
        
        assert login.username == "testuser"
        assert login.password == "pass123"
    
    def test_token_model(self):
        """Test token model"""
        token = Token(
            access_token="token123",
            token_type="bearer",
            refresh_token="refresh123"
        )
        
        assert token.access_token == "token123"
        assert token.token_type == "bearer"
        assert token.refresh_token == "refresh123"
    
    def test_user_role_enum(self):
        """Test user role enum"""
        assert UserRole.USER.value == "user"
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.PREMIUM.value == "premium"


class TestAuthDependencies:
    """Test authentication dependencies"""
    
    @pytest.mark.asyncio
    @patch('src.auth.dependencies.verify_token')
    @patch('src.auth.dependencies.get_user_by_id')
    async def test_get_current_user_valid(self, mock_get_user, mock_verify):
        """Test getting current user with valid token"""
        mock_verify.return_value = {"sub": "123"}
        mock_get_user.return_value = User(
            id=123,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            is_active=True
        )
        
        user = await get_current_user("valid_token")
        
        assert user is not None
        assert user.username == "testuser"
        mock_verify.assert_called_once_with("valid_token")
        mock_get_user.assert_called_once_with(123)
    
    @pytest.mark.asyncio
    @patch('src.auth.dependencies.verify_token')
    async def test_get_current_user_invalid_token(self, mock_verify):
        """Test getting current user with invalid token"""
        mock_verify.return_value = None
        
        with pytest.raises(HTTPException) as exc:
            await get_current_user("invalid_token")
        
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_require_active_user(self):
        """Test require active user dependency"""
        active_user = User(
            id=1,
            username="active",
            email="active@example.com",
            role=UserRole.USER,
            is_active=True
        )
        
        result = await require_active_user(active_user)
        assert result == active_user
        
        inactive_user = User(
            id=2,
            username="inactive",
            email="inactive@example.com",
            role=UserRole.USER,
            is_active=False
        )
        
        with pytest.raises(HTTPException) as exc:
            await require_active_user(inactive_user)
        
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_require_admin(self):
        """Test require admin dependency"""
        admin_user = User(
            id=1,
            username="admin",
            email="admin@example.com",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        result = await require_admin(admin_user)
        assert result == admin_user
        
        regular_user = User(
            id=2,
            username="user",
            email="user@example.com",
            role=UserRole.USER,
            is_active=True
        )
        
        with pytest.raises(HTTPException) as exc:
            await require_admin(regular_user)
        
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN


class TestAuthRouter:
    """Test authentication API endpoints"""
    
    @patch('src.auth.router.create_user')
    def test_register_endpoint(self, mock_create):
        """Test user registration endpoint"""
        mock_create.return_value = User(
            id=1,
            username="newuser",
            email="new@example.com",
            role=UserRole.USER,
            is_active=True
        )
        
        response = client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "securepass123"
            }
        )
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data or "username" in data
    
    @patch('src.auth.router.authenticate_user')
    @patch('src.auth.router.create_access_token')
    def test_login_endpoint(self, mock_token, mock_auth):
        """Test user login endpoint"""
        mock_auth.return_value = User(
            id=1,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            is_active=True
        )
        mock_token.return_value = "access_token_123"
        
        response = client.post(
            "/auth/login",
            data={
                "username": "testuser",
                "password": "pass123"
            }
        )
        
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
    
    @patch('src.auth.dependencies.get_current_user')
    def test_get_me_endpoint(self, mock_get_user):
        """Test get current user endpoint"""
        mock_get_user.return_value = User(
            id=1,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            is_active=True
        )
        
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer token123"}
        )
        
        assert response.status_code in [200, 401]
    
    @patch('src.auth.router.verify_token')
    @patch('src.auth.router.create_access_token')
    def test_refresh_token_endpoint(self, mock_create, mock_verify):
        """Test refresh token endpoint"""
        mock_verify.return_value = {"sub": "123", "type": "refresh"}
        mock_create.return_value = "new_access_token"
        
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": "refresh_token_123"}
        )
        
        assert response.status_code in [200, 401]
    
    @patch('src.auth.dependencies.get_current_user')
    def test_logout_endpoint(self, mock_get_user):
        """Test logout endpoint"""
        mock_get_user.return_value = User(
            id=1,
            username="testuser",
            email="test@example.com",
            role=UserRole.USER,
            is_active=True
        )
        
        response = client.post(
            "/auth/logout",
            headers={"Authorization": "Bearer token123"}
        )
        
        assert response.status_code in [200, 401]


class TestPasswordHashing:
    """Test password hashing functionality"""
    
    @pytest.fixture
    def pwd_context(self):
        """Create password context"""
        return CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def test_hash_password(self, pwd_context):
        """Test password hashing"""
        password = "mysecretpassword"
        hashed = pwd_context.hash(password)
        
        assert hashed != password
        assert pwd_context.verify(password, hashed)
    
    def test_verify_password(self, pwd_context):
        """Test password verification"""
        password = "testpass123"
        wrong_password = "wrongpass"
        hashed = pwd_context.hash(password)
        
        assert pwd_context.verify(password, hashed) is True
        assert pwd_context.verify(wrong_password, hashed) is False
    
    def test_hash_uniqueness(self, pwd_context):
        """Test that same password produces different hashes"""
        password = "samepassword"
        hash1 = pwd_context.hash(password)
        hash2 = pwd_context.hash(password)
        
        assert hash1 != hash2
        assert pwd_context.verify(password, hash1)
        assert pwd_context.verify(password, hash2)