"""Unit tests for RBAC, rate limiting, and security headers middleware.

Tests cover:
- JWT verification and user extraction (auth.py)
- Role-based access control enforcement (auth.py require_roles)
- Rate limit key determination (rate_limit.py)
- Security headers injection (security_headers.py)
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from starlette.requests import Request

from app.config import Settings, get_settings
from app.middleware.auth import get_current_user, require_roles
from app.middleware.rate_limit import get_rate_limit_key, _dynamic_rate_limit
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.models.user import UserRole


# =============================================================================
# Fixtures and Helpers
# =============================================================================

TEST_SECRET = "test-secret-key"
TEST_ALGORITHM = "HS256"


def _make_settings(**overrides) -> Settings:
    """Create test settings with sensible defaults."""
    defaults = {
        "jwt_secret_key": TEST_SECRET,
        "jwt_algorithm": TEST_ALGORITHM,
        "jwt_access_token_expire_minutes": 30,
        "jwt_refresh_token_expire_days": 7,
        "rate_limit_authenticated": 100,
        "rate_limit_unauthenticated": 20,
        "redis_url": "redis://localhost:6379/0",
        "database_url": "postgresql+asyncpg://test:test@localhost/test",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _create_access_token(user_id: str, role: str, expired: bool = False) -> str:
    """Create a JWT access token for testing."""
    now = datetime.now(timezone.utc)
    if expired:
        exp = now - timedelta(hours=1)
    else:
        exp = now + timedelta(minutes=30)

    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "exp": exp,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)


def _create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token for testing."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": now + timedelta(days=7),
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)


def _make_mock_request(authorization: str | None = None, client_ip: str = "127.0.0.1") -> MagicMock:
    """Create a mock request with optional authorization header."""
    request = MagicMock(spec=Request)
    headers = {}
    if authorization:
        headers["authorization"] = authorization
    request.headers = headers
    request.client = MagicMock()
    request.client.host = client_ip
    return request


# =============================================================================
# Tests: Security Headers Middleware
# =============================================================================

class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    def setup_method(self):
        """Set up test app with security headers middleware."""
        self.app = FastAPI()
        self.app.add_middleware(SecurityHeadersMiddleware)

        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        self.client = TestClient(self.app)

    def test_csp_header_present(self):
        """CSP header should be set to default-src 'self'."""
        response = self.client.get("/test")
        assert response.headers["Content-Security-Policy"] == "default-src 'self'"

    def test_x_content_type_options_header(self):
        """X-Content-Type-Options should be nosniff."""
        response = self.client.get("/test")
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options_header(self):
        """X-Frame-Options should be DENY."""
        response = self.client.get("/test")
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_hsts_header(self):
        """HSTS header should enforce HTTPS with 1 year max-age."""
        response = self.client.get("/test")
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    def test_xss_protection_header(self):
        """X-XSS-Protection should be enabled in block mode."""
        response = self.client.get("/test")
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    def test_all_security_headers_present(self):
        """All five security headers should be present on every response."""
        response = self.client.get("/test")
        expected_headers = [
            "Content-Security-Policy",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Strict-Transport-Security",
            "X-XSS-Protection",
        ]
        for header in expected_headers:
            assert header in response.headers, f"Missing header: {header}"


# =============================================================================
# Tests: Rate Limit Key Function
# =============================================================================

class TestRateLimitKey:
    """Tests for rate limiting key extraction logic."""

    @patch("app.middleware.rate_limit.get_settings")
    def test_authenticated_user_keyed_by_user_id(self, mock_settings):
        """Authenticated requests should be keyed by user:{user_id}."""
        mock_settings.return_value = _make_settings()
        user_id = str(uuid.uuid4())
        token = _create_access_token(user_id, "Admin")
        request = _make_mock_request(authorization=f"Bearer {token}")

        key = get_rate_limit_key(request)
        assert key == f"user:{user_id}"

    @patch("app.middleware.rate_limit.get_settings")
    def test_unauthenticated_request_keyed_by_ip(self, mock_settings):
        """Unauthenticated requests should be keyed by client IP."""
        mock_settings.return_value = _make_settings()
        request = _make_mock_request(client_ip="192.168.1.100")

        key = get_rate_limit_key(request)
        assert key == "192.168.1.100"

    @patch("app.middleware.rate_limit.get_settings")
    def test_invalid_token_falls_back_to_ip(self, mock_settings):
        """Requests with invalid tokens should fall back to IP-based keying."""
        mock_settings.return_value = _make_settings()
        request = _make_mock_request(
            authorization="Bearer invalid.token.here",
            client_ip="10.0.0.1",
        )

        key = get_rate_limit_key(request)
        assert key == "10.0.0.1"

    @patch("app.middleware.rate_limit.get_settings")
    def test_expired_token_falls_back_to_ip(self, mock_settings):
        """Requests with expired tokens should fall back to IP-based keying."""
        mock_settings.return_value = _make_settings()
        user_id = str(uuid.uuid4())
        expired_token = _create_access_token(user_id, "Admin", expired=True)
        request = _make_mock_request(
            authorization=f"Bearer {expired_token}",
            client_ip="10.0.0.2",
        )

        key = get_rate_limit_key(request)
        assert key == "10.0.0.2"

    @patch("app.middleware.rate_limit.get_settings")
    def test_dynamic_rate_limit_authenticated(self, mock_settings):
        """Authenticated requests should get 100/minute limit."""
        mock_settings.return_value = _make_settings()
        user_id = str(uuid.uuid4())
        token = _create_access_token(user_id, "Admin")
        request = _make_mock_request(authorization=f"Bearer {token}")

        limit = _dynamic_rate_limit(request)
        assert limit == "100/minute"

    @patch("app.middleware.rate_limit.get_settings")
    def test_dynamic_rate_limit_unauthenticated(self, mock_settings):
        """Unauthenticated requests should get 20/minute limit."""
        mock_settings.return_value = _make_settings()
        request = _make_mock_request()

        limit = _dynamic_rate_limit(request)
        assert limit == "20/minute"


# =============================================================================
# Tests: Auth Middleware (require_roles)
# =============================================================================

class TestRequireRoles:
    """Tests for the require_roles dependency factory."""

    def setup_method(self):
        """Set up test app with role-protected endpoints."""
        self.app = FastAPI()
        self.user_id = str(uuid.uuid4())

        # Mock user for dependency override
        self.mock_user = MagicMock()
        self.mock_user.id = self.user_id
        self.mock_user.role = UserRole.ADMIN.value
        self.mock_user.is_active = True

        # Override get_current_user to return mock user
        async def mock_get_current_user():
            return self.mock_user

        self.app.dependency_overrides[get_current_user] = mock_get_current_user

        # Admin-only endpoint
        @self.app.get("/admin-only")
        async def admin_endpoint(user=Depends(require_roles(UserRole.ADMIN))):
            return {"user_role": user.role}

        # Manager or Admin endpoint
        @self.app.get("/manager-or-admin")
        async def manager_endpoint(
            user=Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
        ):
            return {"user_role": user.role}

        # Salesperson endpoint
        @self.app.get("/sales-only")
        async def sales_endpoint(user=Depends(require_roles(UserRole.SALESPERSON))):
            return {"user_role": user.role}

        self.client = TestClient(self.app)

    def test_admin_can_access_admin_endpoint(self):
        """Admin user should access admin-only endpoint."""
        self.mock_user.role = UserRole.ADMIN.value
        response = self.client.get("/admin-only")
        assert response.status_code == 200
        assert response.json()["user_role"] == "Admin"

    def test_manager_cannot_access_admin_endpoint(self):
        """Manager should be denied access to admin-only endpoint."""
        self.mock_user.role = UserRole.MANAGER.value
        response = self.client.get("/admin-only")
        assert response.status_code == 403

    def test_admin_can_access_manager_or_admin_endpoint(self):
        """Admin should access manager-or-admin endpoint."""
        self.mock_user.role = UserRole.ADMIN.value
        response = self.client.get("/manager-or-admin")
        assert response.status_code == 200

    def test_manager_can_access_manager_or_admin_endpoint(self):
        """Manager should access manager-or-admin endpoint."""
        self.mock_user.role = UserRole.MANAGER.value
        response = self.client.get("/manager-or-admin")
        assert response.status_code == 200

    def test_salesperson_denied_manager_endpoint(self):
        """Salesperson should be denied access to manager-or-admin endpoint."""
        self.mock_user.role = UserRole.SALESPERSON.value
        response = self.client.get("/manager-or-admin")
        assert response.status_code == 403

    def test_storekeeper_denied_sales_endpoint(self):
        """Storekeeper should be denied access to salesperson-only endpoint."""
        self.mock_user.role = UserRole.STOREKEEPER.value
        response = self.client.get("/sales-only")
        assert response.status_code == 403

    def test_salesperson_can_access_sales_endpoint(self):
        """Salesperson should access salesperson-only endpoint."""
        self.mock_user.role = UserRole.SALESPERSON.value
        response = self.client.get("/sales-only")
        assert response.status_code == 200


# =============================================================================
# Tests: Auth Middleware (get_current_user token validation)
# =============================================================================

class TestGetCurrentUser:
    """Tests for JWT token verification in get_current_user."""

    def setup_method(self):
        """Set up test app with a protected endpoint using get_current_user directly."""
        self.app = FastAPI()
        self.user_id = str(uuid.uuid4())
        self.settings = _make_settings()

        @self.app.get("/protected")
        async def protected_endpoint(user=Depends(get_current_user)):
            return {"user_id": str(user.id), "role": user.role}

        self.client = TestClient(self.app)

    def test_missing_authorization_returns_401(self):
        """Request without Authorization header should return 401."""
        # Override settings but not the DB - we need a full override
        self.app.dependency_overrides[get_current_user] = None
        # Remove the override and test directly
        del self.app.dependency_overrides[get_current_user]

        # Use a direct TestClient against a simple app
        app = FastAPI()

        @app.get("/test")
        async def endpoint(user=Depends(get_current_user)):
            return {"user_id": str(user.id)}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

    def test_invalid_token_returns_401(self):
        """Request with invalid token should return 401."""
        app = FastAPI()

        @app.get("/test")
        async def endpoint(user=Depends(get_current_user)):
            return {"user_id": str(user.id)}

        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"Authorization": "Bearer invalid.token.value"},
        )
        assert response.status_code == 401

    def test_refresh_token_rejected(self):
        """Refresh tokens should not be accepted for authentication."""
        app = FastAPI()

        @app.get("/test")
        async def endpoint(user=Depends(get_current_user)):
            return {"user_id": str(user.id)}

        # Override settings dependency
        app.dependency_overrides[get_settings] = lambda: self.settings

        client = TestClient(app)
        refresh_token = _create_refresh_token(self.user_id)
        response = client.get(
            "/test",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert response.status_code == 401
        assert "Invalid token type" in response.json()["detail"]
