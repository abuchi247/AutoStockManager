"""Tests for cookie-based browser refresh authentication.

Covers cookie attributes, cookie-over-body precedence, session rotation on
refresh, cookie expiry plus session revocation on logout, origin validation for
cookie-authenticated state changes, and the retained request-body flow for
non-browser API clients.

Validates: Requirements 3.1, 3.3, 3.4, 3.5
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.dependencies import get_db
from app.middleware.rate_limit import get_rate_limiter
from app.models.user import User, UserRole
from app.routers.auth import router as auth_router
from app.services.auth_service import decode_token, hash_password
from app.services.session_service import SESSION_REGISTRY_PREFIX


TRUSTED_ORIGIN = "https://app.example"
USER_PASSWORD = "TestPass1"


# =============================================================================
# Redis substitute
# =============================================================================


class InMemoryRedis:
    """In-process stand-in for the Redis commands SessionService uses.

    The session registry logic itself is exercised for real; only the network
    transport is replaced so the suite does not require a Redis server.
    """

    def __init__(self) -> None:
        self.sets: dict[str, set[str]] = {}
        self.values: dict[str, Any] = {}

    async def sadd(self, key: str, member: str) -> int:
        members = self.sets.setdefault(key, set())
        before = len(members)
        members.add(member)
        return len(members) - before

    async def srem(self, key: str, member: str) -> int:
        members = self.sets.get(key, set())
        if member in members:
            members.remove(member)
            return 1
        return 0

    async def sismember(self, key: str, member: str) -> bool:
        return member in self.sets.get(key, set())

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    async def expire(self, key: str, ttl: int) -> bool:
        return key in self.sets or key in self.values

    async def set(
        self,
        key: str,
        value: Any,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            removed += self.sets.pop(key, None) is not None
            removed += self.values.pop(key, None) is not None
        return removed


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cookie_settings() -> Settings:
    """Staging-like settings so the cookie is issued with Secure enabled."""
    return Settings(
        environment="staging",
        jwt_secret_key="test-secret-key-for-refresh-cookie-tests",
        jwt_access_token_expire_minutes=30,
        jwt_refresh_token_expire_days=7,
        bcrypt_cost_factor=4,
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        cors_origins=[TRUSTED_ORIGIN],
        frontend_base_url=TRUSTED_ORIGIN,
    )


@pytest.fixture
def redis_stub() -> InMemoryRedis:
    return InMemoryRedis()


class StubDbSession:
    """Async session stand-in for the PostgreSQL user lookup.

    The models use PostgreSQL UUID columns that SQLite cannot render, so the
    database boundary is stubbed while the auth service, session registry, and
    cookie handling all run for real.
    """

    def __init__(self, user: User) -> None:
        self.user = user
        self.added: list[Any] = []

    async def execute(self, *args: Any, **kwargs: Any) -> MagicMock:
        result = MagicMock()
        result.scalar_one_or_none.return_value = self.user
        return result

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


@pytest.fixture
def user(cookie_settings) -> User:
    """An active user that can authenticate."""
    record = MagicMock(spec=User)
    record.id = uuid.uuid4()
    record.username = "cookieuser"
    record.email = "cookie@example.com"
    record.password_hash = hash_password(USER_PASSWORD, cookie_settings)
    record.role = UserRole.ADMIN.value
    record.is_active = True
    record.is_locked = False
    record.locked_until = None
    record.failed_login_attempts = 0
    record.created_at = datetime.now(timezone.utc)
    record.updated_at = datetime.now(timezone.utc)
    return record


@pytest_asyncio.fixture
async def client(
    user,
    cookie_settings,
    redis_stub,
    monkeypatch,
) -> AsyncClient:
    """HTTPS client bound to the auth router with test-scoped dependencies."""

    async def fake_redis_client():
        return redis_stub

    monkeypatch.setattr(
        "app.routers.auth.get_redis_client",
        fake_redis_client,
    )

    limiter = get_rate_limiter()
    previously_enabled = limiter.enabled
    limiter.enabled = False

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = lambda: StubDbSession(user)
    app.dependency_overrides[get_settings] = lambda: cookie_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=TRUSTED_ORIGIN) as http_client:
        yield http_client

    limiter.enabled = previously_enabled


# =============================================================================
# Helpers
# =============================================================================


async def _login(client: AsyncClient, cookie_settings: Settings) -> str:
    """Log in and return the refresh credential the server set in the cookie."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "cookieuser", "password": USER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return client.cookies[cookie_settings.refresh_cookie_name]


def _set_cookie_header(response, cookie_name: str) -> str:
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(f"{cookie_name}="):
            return header
    raise AssertionError(f"No Set-Cookie header for {cookie_name}: {response.headers}")


async def _active_jtis(redis_stub: InMemoryRedis, user: User) -> set[str]:
    return await redis_stub.smembers(f"{SESSION_REGISTRY_PREFIX}{user.id}")


def _jti(token: str, settings: Settings) -> str:
    return decode_token(token, settings)["jti"]


# =============================================================================
# Cookie issuance (Requirements 3.1, 3.5)
# =============================================================================


class TestLoginCookie:
    @pytest.mark.asyncio
    async def test_login_sets_hardened_refresh_cookie(
        self, client, user, cookie_settings
    ):
        """Requirement 3.1: HTTP-only, Secure, SameSite cookie on a narrow path."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "cookieuser", "password": USER_PASSWORD},
        )

        assert response.status_code == 200, response.text
        header = _set_cookie_header(response, cookie_settings.refresh_cookie_name)
        lowered = header.lower()
        assert "httponly" in lowered
        assert "secure" in lowered
        assert "samesite=strict" in lowered
        assert f"path={cookie_settings.refresh_cookie_path}" in lowered
        assert "max-age=604800" in lowered

    @pytest.mark.asyncio
    async def test_login_response_body_has_no_refresh_credential(
        self, client, user, cookie_settings
    ):
        """Requirement 3.5: refresh credentials stay out of JSON responses."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "cookieuser", "password": USER_PASSWORD},
        )

        payload = response.json()
        assert payload["access_token"]
        assert payload["token_type"] == "bearer"
        assert "refresh_token" not in payload
        # The cookie carries the credential instead.
        assert client.cookies[cookie_settings.refresh_cookie_name]


# =============================================================================
# Refresh (Requirements 3.3, 3.5)
# =============================================================================


class TestCookieRefresh:
    @pytest.mark.asyncio
    async def test_refresh_without_body_rotates_cookie_and_session(
        self, client, user, cookie_settings, redis_stub
    ):
        """Requirement 3.3: the cookie alone refreshes the access token."""
        original_token = await _login(client, cookie_settings)
        original_jti = _jti(original_token, cookie_settings)

        # A browser on the configured frontend origin is accepted.
        response = await client.post(
            "/api/v1/auth/refresh",
            headers={"Origin": TRUSTED_ORIGIN},
        )

        assert response.status_code == 200, response.text
        assert "refresh_token" not in response.json()
        rotated_token = client.cookies[cookie_settings.refresh_cookie_name]
        assert rotated_token != original_token

        active = await _active_jtis(redis_stub, user)
        assert original_jti not in active
        assert _jti(rotated_token, cookie_settings) in active

    @pytest.mark.asyncio
    async def test_cookie_takes_precedence_over_body_token(
        self, client, user, cookie_settings, redis_stub
    ):
        """A body token cannot override the browser's own cookie session."""
        other_token = await _login(client, cookie_settings)
        other_jti = _jti(other_token, cookie_settings)
        client.cookies.clear()

        cookie_token = await _login(client, cookie_settings)
        cookie_jti = _jti(cookie_token, cookie_settings)

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": other_token},
        )

        assert response.status_code == 200, response.text
        active = await _active_jtis(redis_stub, user)
        # The cookie session was the one rotated; the body token is untouched.
        assert cookie_jti not in active
        assert other_jti in active

    @pytest.mark.asyncio
    async def test_body_token_still_works_for_non_browser_clients(
        self, client, user, cookie_settings, redis_stub
    ):
        """Requirement 3.5: the request-body flow remains available."""
        token = await _login(client, cookie_settings)
        client.cookies.clear()

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token},
        )

        assert response.status_code == 200, response.text
        assert response.json()["access_token"]
        active = await _active_jtis(redis_stub, user)
        assert _jti(token, cookie_settings) not in active

    @pytest.mark.asyncio
    async def test_refresh_without_any_credential_is_unauthorized(self, client, user):
        """A missing credential is an auth failure, not a validation error."""
        response = await client.post("/api/v1/auth/refresh")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_rejected_cookie_is_expired(self, client, user, cookie_settings):
        """An unusable cookie is cleared so the browser stops replaying it."""
        client.cookies.set(
            cookie_settings.refresh_cookie_name,
            "not-a-jwt",
            domain="app.example",
            path=cookie_settings.refresh_cookie_path,
        )

        response = await client.post("/api/v1/auth/refresh")

        assert response.status_code == 401
        header = _set_cookie_header(response, cookie_settings.refresh_cookie_name)
        assert "Max-Age=0" in header

    @pytest.mark.asyncio
    async def test_untrusted_origin_is_rejected_for_cookie_auth(
        self, client, user, cookie_settings, redis_stub
    ):
        """Cookie-authenticated state changes require a trusted origin (CSRF)."""
        token = await _login(client, cookie_settings)

        response = await client.post(
            "/api/v1/auth/refresh",
            headers={"Origin": "https://evil.example"},
        )

        assert response.status_code == 403
        # The session survives a rejected cross-site attempt.
        active = await _active_jtis(redis_stub, user)
        assert _jti(token, cookie_settings) in active


# =============================================================================
# Logout (Requirement 3.4)
# =============================================================================


class TestNonBrowserClientProcedure:
    """The documented rollout procedure for clients that ignore cookies.

    Login only ever delivers the refresh credential in ``Set-Cookie``, so a
    non-browser client obtains it from that header and then keeps using the
    request-body flow. This is the compatibility path described in
    OPERATIONS_RUNBOOK.md section 5.
    """

    @pytest.mark.asyncio
    async def test_api_client_can_complete_login_refresh_logout_via_body(
        self, client, user, cookie_settings, redis_stub
    ):
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "cookieuser", "password": USER_PASSWORD},
        )
        assert login.status_code == 200, login.text

        # A cookie-less client reads the credential from the response header.
        header = _set_cookie_header(login, cookie_settings.refresh_cookie_name)
        credential = header.split(";", 1)[0].split("=", 1)[1]
        client.cookies.clear()

        refreshed = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": credential},
        )
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["access_token"]

        rotated_header = _set_cookie_header(
            refreshed, cookie_settings.refresh_cookie_name
        )
        rotated = rotated_header.split(";", 1)[0].split("=", 1)[1]
        assert rotated != credential
        client.cookies.clear()

        logged_out = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": rotated},
        )
        assert logged_out.status_code == 200, logged_out.text
        assert await _active_jtis(redis_stub, user) == set()


class TestCookieLogout:
    @pytest.mark.asyncio
    async def test_logout_expires_cookie_and_revokes_session(
        self, client, user, cookie_settings, redis_stub
    ):
        """Requirement 3.4: clear the cookie and invalidate the session entry."""
        await _login(client, cookie_settings)

        response = await client.post("/api/v1/auth/logout")

        assert response.status_code == 200, response.text
        header = _set_cookie_header(response, cookie_settings.refresh_cookie_name)
        assert "Max-Age=0" in header
        assert cookie_settings.refresh_cookie_name not in client.cookies
        assert await _active_jtis(redis_stub, user) == set()

    @pytest.mark.asyncio
    async def test_logout_without_credential_still_clears_cookie(
        self, client, user, cookie_settings
    ):
        """Body-less logout from an already-cleared client stays successful."""
        response = await client.post("/api/v1/auth/logout")

        assert response.status_code == 200, response.text
        header = _set_cookie_header(response, cookie_settings.refresh_cookie_name)
        assert "Max-Age=0" in header

    @pytest.mark.asyncio
    async def test_logout_accepts_body_token_from_non_browser_clients(
        self, client, user, cookie_settings, redis_stub
    ):
        """Requirement 3.5: non-browser clients keep the request-body flow."""
        token = await _login(client, cookie_settings)
        client.cookies.clear()

        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": token},
        )

        assert response.status_code == 200, response.text
        assert await _active_jtis(redis_stub, user) == set()


# =============================================================================
# Cookie configuration
# =============================================================================


class TestRefreshCookieSettings:
    def test_secure_is_derived_from_environment(self):
        """Local development runs over plain HTTP; deployed environments do not."""
        development = Settings(
            environment="development",
            database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        )
        staging = Settings(
            environment="staging",
            database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        )

        assert development.refresh_cookie_secure_enabled is False
        assert staging.refresh_cookie_secure_enabled is True

    def test_explicit_secure_setting_wins(self):
        settings = Settings(
            environment="development",
            refresh_cookie_secure=True,
            database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        )

        assert settings.refresh_cookie_secure_enabled is True

    def test_production_rejects_non_secure_refresh_cookie(self):
        with pytest.raises(ValueError) as excinfo:
            Settings(
                environment="production",
                jwt_secret_key="a" * 48,
                postgres_password="a-strong-production-password",
                refresh_cookie_secure=False,
                database_url=(
                    "postgresql+asyncpg://app:a-strong-production-password"
                    "@db:5432/auto_erp"
                ),
            )

        assert "refresh_cookie_secure" in str(excinfo.value)
