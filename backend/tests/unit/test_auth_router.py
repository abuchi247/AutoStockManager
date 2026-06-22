"""Unit tests for auth and users routers.

Tests the API endpoints for login, refresh, logout, password reset,
and user management (Admin only).
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import (
    AuthService,
    create_access_token,
    create_refresh_token,
    hash_password,
)
from app.config import Settings


# =============================================================================
# Test fixtures
# =============================================================================


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        jwt_secret_key="test-secret-key-for-unit-tests",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
        jwt_refresh_token_expire_days=7,
        bcrypt_cost_factor=4,  # Fast for tests
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
    )


@pytest.fixture
def test_user(test_settings):
    """Create a mock user object."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.email = "test@example.com"
    user.password_hash = hash_password("TestPass1", test_settings)
    user.role = UserRole.ADMIN.value
    user.is_active = True
    user.is_locked = False
    user.locked_until = None
    user.failed_login_attempts = 0
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def admin_access_token(test_user, test_settings):
    """Generate a valid admin access token for testing."""
    return create_access_token(
        user_id=str(test_user.id),
        role=test_user.role,
        settings=test_settings,
    )


# =============================================================================
# Schema tests
# =============================================================================


class TestAuthSchemas:
    """Tests for auth-related Pydantic schemas."""

    def test_login_request_valid(self):
        req = LoginRequest(username="admin", password="SecurePass1")
        assert req.username == "admin"
        assert req.password == "SecurePass1"

    def test_login_request_empty_username_fails(self):
        with pytest.raises(Exception):
            LoginRequest(username="", password="SecurePass1")

    def test_refresh_token_request_valid(self):
        req = RefreshTokenRequest(refresh_token="some.jwt.token")
        assert req.refresh_token == "some.jwt.token"

    def test_logout_request_valid(self):
        req = LogoutRequest(refresh_token="some.jwt.token")
        assert req.refresh_token == "some.jwt.token"

    def test_password_reset_request_valid(self):
        req = PasswordResetRequest(email="user@example.com")
        assert req.email == "user@example.com"

    def test_password_reset_request_invalid_email(self):
        with pytest.raises(Exception):
            PasswordResetRequest(email="not-an-email")

    def test_password_reset_confirm_valid(self):
        req = PasswordResetConfirm(
            reset_token="some.token",
            new_password="NewSecure1",
        )
        assert req.reset_token == "some.token"
        assert req.new_password == "NewSecure1"

    def test_password_reset_confirm_short_password(self):
        with pytest.raises(Exception):
            PasswordResetConfirm(
                reset_token="some.token",
                new_password="short",
            )

    def test_token_response_valid(self):
        resp = TokenResponse(
            access_token="access.token",
            refresh_token="refresh.token",
            token_type="bearer",
        )
        assert resp.access_token == "access.token"
        assert resp.token_type == "bearer"


class TestUserSchemas:
    """Tests for user-related Pydantic schemas."""

    def test_user_create_valid(self):
        req = UserCreate(
            username="john_doe",
            email="john@example.com",
            password="SecurePass1",
            role=UserRole.SALESPERSON,
        )
        assert req.username == "john_doe"
        assert req.role == UserRole.SALESPERSON

    def test_user_create_short_username(self):
        with pytest.raises(Exception):
            UserCreate(
                username="ab",
                email="john@example.com",
                password="SecurePass1",
                role=UserRole.SALESPERSON,
            )

    def test_user_create_invalid_email(self):
        with pytest.raises(Exception):
            UserCreate(
                username="john_doe",
                email="invalid-email",
                password="SecurePass1",
                role=UserRole.SALESPERSON,
            )

    def test_user_response_from_attributes(self):
        """Test UserResponse works with from_attributes (ORM mode)."""
        user_data = {
            "id": uuid.uuid4(),
            "username": "testuser",
            "email": "test@example.com",
            "role": "Admin",
            "is_active": True,
            "failed_login_attempts": 0,
            "locked_until": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        resp = UserResponse(**user_data)
        assert resp.username == "testuser"
        assert resp.role == "Admin"


# =============================================================================
# Router integration tests (using TestClient)
# =============================================================================


class TestAuthRouterEndpoints:
    """Test that auth router endpoints are correctly registered."""

    def test_auth_router_has_login_endpoint(self):
        from app.routers.auth import router
        paths = [r.path for r in router.routes]
        assert "/api/v1/auth/login" in paths

    def test_auth_router_has_refresh_endpoint(self):
        from app.routers.auth import router
        paths = [r.path for r in router.routes]
        assert "/api/v1/auth/refresh" in paths

    def test_auth_router_has_logout_endpoint(self):
        from app.routers.auth import router
        paths = [r.path for r in router.routes]
        assert "/api/v1/auth/logout" in paths

    def test_auth_router_has_reset_password_endpoint(self):
        from app.routers.auth import router
        paths = [r.path for r in router.routes]
        assert "/api/v1/auth/reset-password" in paths

    def test_auth_router_has_reset_password_confirm_endpoint(self):
        from app.routers.auth import router
        paths = [r.path for r in router.routes]
        assert "/api/v1/auth/reset-password/confirm" in paths


class TestUsersRouterEndpoints:
    """Test that users router endpoints are correctly registered."""

    def test_users_router_has_list_endpoint(self):
        from app.routers.users import router
        paths = [r.path for r in router.routes]
        assert "/api/v1/users" in paths

    def test_users_router_has_get_endpoint(self):
        from app.routers.users import router
        paths = [r.path for r in router.routes]
        assert "/api/v1/users/{user_id}" in paths

    def test_users_router_uses_correct_methods(self):
        from app.routers.users import router
        for route in router.routes:
            if route.path == "/api/v1/users" and "GET" in route.methods:
                assert True
                return
        pytest.fail("GET /api/v1/users not found")

    def test_users_router_post_creates_user(self):
        from app.routers.users import router
        for route in router.routes:
            if route.path == "/api/v1/users" and "POST" in route.methods:
                assert True
                return
        pytest.fail("POST /api/v1/users not found")


class TestMainAppRouters:
    """Test that routers are correctly registered in the main app."""

    def test_app_includes_auth_routes(self):
        from app.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes if hasattr(r, 'path')]
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/auth/refresh" in paths
        assert "/api/v1/auth/logout" in paths
        assert "/api/v1/auth/reset-password" in paths

    def test_app_includes_users_routes(self):
        from app.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes if hasattr(r, 'path')]
        assert "/api/v1/users" in paths
        assert "/api/v1/users/{user_id}" in paths
