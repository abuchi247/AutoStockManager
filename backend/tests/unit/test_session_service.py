"""
Unit tests for the session registry and login history service.

Tests Requirements:
- 17.3: Session registry tracking active refresh tokens per user
- 17.4: Logout invalidates refresh token and removes from registry
- 17.5: Login history records (timestamp, IP, user agent, success/failure)
- 17.6: Admin session revocation (invalidate all refresh tokens for a user)
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.config import Settings
from app.models.login_history import LoginHistory
from app.services.session_service import (
    SESSION_REGISTRY_PREFIX,
    SESSION_TOKEN_PREFIX,
    SessionService,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def settings():
    """Test settings with short token expiry."""
    return Settings(
        jwt_secret_key="test-secret-key",
        jwt_refresh_token_expire_days=7,
        redis_url="redis://localhost:6379/0",
    )


@pytest.fixture
def mock_redis():
    """Mock async Redis client."""
    redis = AsyncMock()
    redis.sadd = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.set = AsyncMock(return_value=True)
    redis.sismember = AsyncMock(return_value=True)
    redis.srem = AsyncMock(return_value=1)
    redis.delete = AsyncMock(return_value=1)
    redis.smembers = AsyncMock(return_value=set())
    redis.get = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def mock_db():
    """Mock async SQLAlchemy session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def session_service(mock_db, mock_redis, settings):
    """SessionService instance with mocked dependencies."""
    return SessionService(db=mock_db, redis_client=mock_redis, settings=settings)


# =============================================================================
# Session Registry Tests (Requirement 17.3)
# =============================================================================


class TestSessionRegistry:
    """Tests for the Redis session registry."""

    @pytest.mark.asyncio
    async def test_register_session_adds_jti_to_user_set(
        self, session_service, mock_redis, settings
    ):
        """Requirement 17.3: Session is registered with JTI in user's Redis SET."""
        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())

        await session_service.register_session(
            user_id=user_id,
            jti=jti,
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
        )

        # Verify JTI added to user's session set
        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"
        mock_redis.sadd.assert_called_once_with(user_key, jti)

        # Verify TTL set
        ttl = settings.jwt_refresh_token_expire_days * 86400
        mock_redis.expire.assert_called_once_with(user_key, ttl)

    @pytest.mark.asyncio
    async def test_register_session_stores_metadata(
        self, session_service, mock_redis, settings
    ):
        """Requirement 17.3: Session metadata is stored in Redis."""
        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())

        await session_service.register_session(
            user_id=user_id,
            jti=jti,
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
        )

        # Verify session metadata stored
        token_key = f"{SESSION_TOKEN_PREFIX}{jti}"
        ttl = settings.jwt_refresh_token_expire_days * 86400
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == token_key
        metadata = json.loads(call_args[0][1])
        assert metadata["user_id"] == user_id
        assert metadata["jti"] == jti
        assert metadata["ip_address"] == "10.0.0.1"
        assert metadata["user_agent"] == "Mozilla/5.0"
        assert "created_at" in metadata
        assert call_args[1]["ex"] == ttl

    @pytest.mark.asyncio
    async def test_is_session_valid_returns_true_for_active(
        self, session_service, mock_redis
    ):
        """Requirement 17.3: Active session is correctly identified."""
        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())
        mock_redis.sismember.return_value = True

        result = await session_service.is_session_valid(user_id, jti)

        assert result is True
        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"
        mock_redis.sismember.assert_called_once_with(user_key, jti)

    @pytest.mark.asyncio
    async def test_is_session_valid_returns_false_for_revoked(
        self, session_service, mock_redis
    ):
        """Requirement 17.3: Revoked session is correctly identified."""
        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())
        mock_redis.sismember.return_value = False

        result = await session_service.is_session_valid(user_id, jti)

        assert result is False


# =============================================================================
# Logout / Session Removal Tests (Requirement 17.4)
# =============================================================================


class TestSessionRemoval:
    """Tests for session removal on logout."""

    @pytest.mark.asyncio
    async def test_remove_session_deletes_jti_from_user_set(
        self, session_service, mock_redis
    ):
        """Requirement 17.4: Logout removes JTI from user's session set."""
        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())

        await session_service.remove_session(user_id, jti)

        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"
        mock_redis.srem.assert_called_once_with(user_key, jti)

    @pytest.mark.asyncio
    async def test_remove_session_deletes_token_metadata(
        self, session_service, mock_redis
    ):
        """Requirement 17.4: Logout deletes token metadata from Redis."""
        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())

        await session_service.remove_session(user_id, jti)

        token_key = f"{SESSION_TOKEN_PREFIX}{jti}"
        mock_redis.delete.assert_called_once_with(token_key)


# =============================================================================
# Admin Session Revocation Tests (Requirement 17.6)
# =============================================================================


class TestAdminRevocation:
    """Tests for admin-initiated session revocation."""

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_removes_all_jtis(
        self, session_service, mock_redis
    ):
        """Requirement 17.6: Admin revocation removes all active sessions."""
        user_id = str(uuid.uuid4())
        jti1 = str(uuid.uuid4())
        jti2 = str(uuid.uuid4())
        jti3 = str(uuid.uuid4())
        mock_redis.smembers.return_value = {jti1, jti2, jti3}

        revoked = await session_service.revoke_all_sessions(user_id)

        assert revoked == 3

        # Verify all token metadata keys deleted
        expected_keys = [
            f"{SESSION_TOKEN_PREFIX}{jti1}",
            f"{SESSION_TOKEN_PREFIX}{jti2}",
            f"{SESSION_TOKEN_PREFIX}{jti3}",
        ]
        # delete is called with all token keys then the user key
        delete_calls = mock_redis.delete.call_args_list
        # First call: delete token keys
        token_delete_args = set(delete_calls[0][0])
        assert token_delete_args == set(expected_keys)
        # Second call: delete user session set
        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"
        assert delete_calls[1][0][0] == user_key

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_empty_set(
        self, session_service, mock_redis
    ):
        """Requirement 17.6: Revocation with no active sessions returns 0."""
        user_id = str(uuid.uuid4())
        mock_redis.smembers.return_value = set()

        revoked = await session_service.revoke_all_sessions(user_id)

        assert revoked == 0
        # Only the user key deletion is called (no token keys to delete)
        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"
        mock_redis.delete.assert_called_once_with(user_key)

    @pytest.mark.asyncio
    async def test_get_active_sessions_returns_metadata(
        self, session_service, mock_redis
    ):
        """Requirement 17.3: Can retrieve list of active sessions for a user."""
        user_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())
        mock_redis.smembers.return_value = {jti}
        session_data = {
            "user_id": user_id,
            "jti": jti,
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent",
            "created_at": "2025-01-01T00:00:00+00:00",
        }
        mock_redis.get.return_value = json.dumps(session_data)

        sessions = await session_service.get_active_sessions(user_id)

        assert len(sessions) == 1
        assert sessions[0]["jti"] == jti
        assert sessions[0]["ip_address"] == "192.168.1.1"


# =============================================================================
# Login History Tests (Requirement 17.5)
# =============================================================================


class TestLoginHistory:
    """Tests for login history recording."""

    @pytest.mark.asyncio
    async def test_record_successful_login(self, session_service, mock_db):
        """Requirement 17.5: Successful login is recorded with all context."""
        user_id = uuid.uuid4()

        record = await session_service.record_login_attempt(
            username="testuser",
            success=True,
            user_id=user_id,
            ip_address="192.168.1.100",
            user_agent="Chrome/120.0",
        )

        assert record.username == "testuser"
        assert record.success is True
        assert record.user_id == user_id
        assert record.ip_address == "192.168.1.100"
        assert record.user_agent == "Chrome/120.0"
        assert record.failure_reason is None
        mock_db.add.assert_called_once_with(record)
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_failed_login_with_reason(self, session_service, mock_db):
        """Requirement 17.5: Failed login is recorded with failure reason."""
        record = await session_service.record_login_attempt(
            username="baduser",
            success=False,
            ip_address="10.0.0.5",
            user_agent="curl/7.0",
            failure_reason="User not found",
        )

        assert record.username == "baduser"
        assert record.success is False
        assert record.user_id is None
        assert record.failure_reason == "User not found"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_login_attempt_with_no_optional_fields(
        self, session_service, mock_db
    ):
        """Requirement 17.5: Login can be recorded with minimal information."""
        record = await session_service.record_login_attempt(
            username="minimaluser",
            success=False,
            failure_reason="Invalid password",
        )

        assert record.username == "minimaluser"
        assert record.success is False
        assert record.ip_address is None
        assert record.user_agent is None


# =============================================================================
# Login History Model Tests
# =============================================================================


class TestLoginHistoryModel:
    """Tests for the LoginHistory SQLAlchemy model."""

    def test_login_history_repr_success(self):
        """Test string representation of a successful login."""
        record = LoginHistory(
            id=uuid.uuid4(),
            username="testuser",
            success=True,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        repr_str = repr(record)
        assert "testuser" in repr_str
        assert "success" in repr_str

    def test_login_history_repr_failure(self):
        """Test string representation of a failed login."""
        record = LoginHistory(
            id=uuid.uuid4(),
            username="baduser",
            success=False,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        repr_str = repr(record)
        assert "baduser" in repr_str
        assert "failed" in repr_str
