"""Unit tests for the authentication service."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

from app.config import Settings
from app.models.user import User, UserRole
from app.services.auth_service import (
    AccountLockedError,
    AuthenticationError,
    AuthService,
    PasswordValidationError,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_complexity,
    verify_password,
)


# =============================================================================
# Test Settings
# =============================================================================

def _test_settings() -> Settings:
    """Create test settings with fast bcrypt (lower cost for speed)."""
    return Settings(
        jwt_secret_key="test-secret-key-for-unit-tests",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
        jwt_refresh_token_expire_days=7,
        bcrypt_cost_factor=4,  # Low cost factor for fast tests
        account_lockout_threshold=5,
        account_lockout_window_minutes=15,
        account_lockout_duration_minutes=30,
        database_url="postgresql+asyncpg://test:test@localhost/test",
    )


# =============================================================================
# Password Hashing Tests (Requirement 2.7)
# =============================================================================


class TestPasswordHashing:
    """Test bcrypt password hashing."""

    def test_hash_password_returns_bcrypt_hash(self):
        """hash_password should return a bcrypt hash string."""
        settings = _test_settings()
        hashed = hash_password("MyPassword1", settings)
        assert hashed.startswith("$2b$")

    def test_hash_password_different_each_time(self):
        """hash_password should produce different hashes for the same input (salt)."""
        settings = _test_settings()
        hash1 = hash_password("MyPassword1", settings)
        hash2 = hash_password("MyPassword1", settings)
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """verify_password should return True for correct password."""
        settings = _test_settings()
        hashed = hash_password("MyPassword1", settings)
        assert verify_password("MyPassword1", hashed, settings) is True

    def test_verify_password_incorrect(self):
        """verify_password should return False for incorrect password."""
        settings = _test_settings()
        hashed = hash_password("MyPassword1", settings)
        assert verify_password("WrongPassword1", hashed, settings) is False

    def test_hash_uses_configured_cost_factor(self):
        """The hash should use the configured cost factor from settings."""
        settings = _test_settings()
        settings.bcrypt_cost_factor = 4
        hashed = hash_password("MyPassword1", settings)
        # bcrypt hash format: $2b$<cost>$<salt+hash>
        assert "$2b$04$" in hashed


# =============================================================================
# Password Complexity Tests (Requirement 2.5)
# =============================================================================


class TestPasswordComplexity:
    """Test password complexity validation."""

    def test_valid_password(self):
        """A password meeting all requirements should pass."""
        is_valid, msg = validate_password_complexity("MyPass12")
        assert is_valid is True
        assert msg == ""

    def test_too_short(self):
        """Password shorter than 8 chars should fail."""
        is_valid, msg = validate_password_complexity("Ab1cdef")
        assert is_valid is False
        assert "8 characters" in msg

    def test_no_uppercase(self):
        """Password without uppercase should fail."""
        is_valid, msg = validate_password_complexity("mypass12")
        assert is_valid is False
        assert "uppercase" in msg

    def test_no_lowercase(self):
        """Password without lowercase should fail."""
        is_valid, msg = validate_password_complexity("MYPASS12")
        assert is_valid is False
        assert "lowercase" in msg

    def test_no_digit(self):
        """Password without digit should fail."""
        is_valid, msg = validate_password_complexity("MyPasswd")
        assert is_valid is False
        assert "digit" in msg

    def test_exactly_8_chars_valid(self):
        """Password with exactly 8 chars meeting all requirements should pass."""
        is_valid, msg = validate_password_complexity("Abcdefg1")
        assert is_valid is True

    def test_empty_password(self):
        """Empty password should fail."""
        is_valid, msg = validate_password_complexity("")
        assert is_valid is False


# =============================================================================
# JWT Token Tests (Requirements 2.2, 2.3, 2.4)
# =============================================================================


class TestAccessToken:
    """Test JWT access token creation and validation."""

    def test_create_access_token_valid(self):
        """create_access_token should return a valid JWT."""
        settings = _test_settings()
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id, "Admin", settings)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        assert payload["sub"] == user_id
        assert payload["role"] == "Admin"
        assert payload["type"] == "access"

    def test_access_token_has_expiration(self):
        """Access token should have an exp claim."""
        settings = _test_settings()
        token = create_access_token(str(uuid.uuid4()), "Manager", settings)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        assert "exp" in payload

    def test_access_token_has_jti(self):
        """Access token should include a unique jti claim."""
        settings = _test_settings()
        token1 = create_access_token(str(uuid.uuid4()), "Admin", settings)
        token2 = create_access_token(str(uuid.uuid4()), "Admin", settings)
        payload1 = jwt.decode(token1, settings.jwt_secret_key, algorithms=["HS256"])
        payload2 = jwt.decode(token2, settings.jwt_secret_key, algorithms=["HS256"])
        assert payload1["jti"] != payload2["jti"]


class TestRefreshToken:
    """Test JWT refresh token creation and validation."""

    def test_create_refresh_token_valid(self):
        """create_refresh_token should return a valid JWT with type=refresh."""
        settings = _test_settings()
        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id, settings)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_refresh_token_longer_expiry(self):
        """Refresh token should expire later than access token."""
        settings = _test_settings()
        user_id = str(uuid.uuid4())
        access = create_access_token(user_id, "Admin", settings)
        refresh = create_refresh_token(user_id, settings)
        access_payload = jwt.decode(access, settings.jwt_secret_key, algorithms=["HS256"])
        refresh_payload = jwt.decode(refresh, settings.jwt_secret_key, algorithms=["HS256"])
        assert refresh_payload["exp"] > access_payload["exp"]


class TestPasswordResetToken:
    """Test password reset token generation (Requirement 2.4)."""

    def test_create_reset_token(self):
        """create_password_reset_token should return a JWT with type=password_reset."""
        settings = _test_settings()
        user_id = str(uuid.uuid4())
        token = create_password_reset_token(user_id, settings)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        assert payload["sub"] == user_id
        assert payload["type"] == "password_reset"

    def test_reset_token_has_expiration(self):
        """Reset token should expire (time-limited)."""
        settings = _test_settings()
        token = create_password_reset_token(str(uuid.uuid4()), settings)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        assert "exp" in payload


class TestDecodeToken:
    """Test token decoding utility."""

    def test_decode_valid_token(self):
        """decode_token should return payload for a valid token."""
        settings = _test_settings()
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id, "Admin", settings)
        payload = decode_token(token, settings)
        assert payload["sub"] == user_id

    def test_decode_invalid_token_raises(self):
        """decode_token should raise JWTError for an invalid token."""
        from jose import JWTError

        settings = _test_settings()
        with pytest.raises(JWTError):
            decode_token("invalid.token.string", settings)

    def test_decode_wrong_secret_raises(self):
        """decode_token should raise JWTError if secret doesn't match."""
        from jose import JWTError

        settings = _test_settings()
        token = create_access_token(str(uuid.uuid4()), "Admin", settings)
        wrong_settings = _test_settings()
        wrong_settings.jwt_secret_key = "wrong-secret"
        with pytest.raises(JWTError):
            decode_token(token, wrong_settings)


# =============================================================================
# AuthService Tests (Requirements 2.2, 2.3, 2.4, 2.8)
# =============================================================================


def _make_user(
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "TestPass1",
    role: str = UserRole.ADMIN.value,
    is_active: bool = True,
    locked_until=None,
    failed_login_attempts: int = 0,
) -> User:
    """Create a test User instance with a hashed password."""
    settings = _test_settings()
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password, settings),
        role=role,
        is_active=is_active,
        failed_login_attempts=failed_login_attempts,
        locked_until=locked_until,
    )
    user.id = uuid.uuid4()
    user.deleted_at = None
    return user


def _mock_db_with_user(user):
    """Create a mock AsyncSession that returns the given user on select queries."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    return db


class TestAuthServiceLogin:
    """Test AuthService.login (Requirements 2.2, 2.8)."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Successful login should return access and refresh tokens."""
        settings = _test_settings()
        user = _make_user(password="TestPass1")
        db = _mock_db_with_user(user)

        service = AuthService(db, settings)
        result = await service.login("testuser", "TestPass1")

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        """Wrong password should raise AuthenticationError."""
        settings = _test_settings()
        user = _make_user(password="TestPass1")
        db = _mock_db_with_user(user)

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError):
            await service.login("testuser", "WrongPass1")

    @pytest.mark.asyncio
    async def test_login_user_not_found(self):
        """Non-existent user should raise AuthenticationError."""
        settings = _test_settings()
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError):
            await service.login("nonexistent", "TestPass1")

    @pytest.mark.asyncio
    async def test_login_inactive_user(self):
        """Inactive user should raise AuthenticationError."""
        settings = _test_settings()
        user = _make_user(is_active=False)
        db = _mock_db_with_user(user)

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError):
            await service.login("testuser", "TestPass1")

    @pytest.mark.asyncio
    async def test_login_locked_account(self):
        """Locked account should raise AccountLockedError."""
        settings = _test_settings()
        user = _make_user()
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        db = _mock_db_with_user(user)

        service = AuthService(db, settings)
        with pytest.raises(AccountLockedError):
            await service.login("testuser", "TestPass1")

    @pytest.mark.asyncio
    async def test_login_increments_failed_attempts(self):
        """Failed login should increment failed_login_attempts."""
        settings = _test_settings()
        user = _make_user(password="TestPass1")
        db = _mock_db_with_user(user)

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError):
            await service.login("testuser", "WrongPass1")

        assert user.failed_login_attempts == 1

    @pytest.mark.asyncio
    async def test_login_locks_after_threshold(self):
        """Account should lock after 5 failed attempts (Requirement 2.8)."""
        settings = _test_settings()
        user = _make_user(password="TestPass1", failed_login_attempts=4)
        db = _mock_db_with_user(user)

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError):
            await service.login("testuser", "WrongPass1")

        assert user.failed_login_attempts == 5
        assert user.locked_until is not None
        assert user.locked_until > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_login_resets_attempts_on_success(self):
        """Successful login should reset failed_login_attempts to 0."""
        settings = _test_settings()
        user = _make_user(password="TestPass1", failed_login_attempts=3)
        db = _mock_db_with_user(user)

        service = AuthService(db, settings)
        await service.login("testuser", "TestPass1")

        assert user.failed_login_attempts == 0
        assert user.locked_until is None


class TestAuthServiceRefresh:
    """Test AuthService.refresh_token (Requirement 2.3)."""

    @pytest.mark.asyncio
    async def test_refresh_success(self):
        """Valid refresh token should return new token pair."""
        settings = _test_settings()
        user = _make_user()
        db = _mock_db_with_user(user)

        refresh = create_refresh_token(str(user.id), settings)

        service = AuthService(db, settings)
        result = await service.refresh_token(refresh)

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self):
        """Invalid token should raise AuthenticationError."""
        settings = _test_settings()
        db = AsyncMock()

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError):
            await service.refresh_token("invalid.token")

    @pytest.mark.asyncio
    async def test_refresh_access_token_rejected(self):
        """Using an access token for refresh should be rejected."""
        settings = _test_settings()
        user = _make_user()
        db = _mock_db_with_user(user)

        access = create_access_token(str(user.id), user.role, settings)

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError, match="Invalid token type"):
            await service.refresh_token(access)


class TestAuthServiceLogout:
    """Test AuthService.logout."""

    @pytest.mark.asyncio
    async def test_logout_success(self):
        """Valid refresh token should be accepted for logout."""
        settings = _test_settings()
        user = _make_user()
        db = AsyncMock()

        refresh = create_refresh_token(str(user.id), settings)

        service = AuthService(db, settings)
        result = await service.logout(refresh)
        assert "message" in result

    @pytest.mark.asyncio
    async def test_logout_invalid_token(self):
        """Invalid token should raise AuthenticationError on logout."""
        settings = _test_settings()
        db = AsyncMock()

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError):
            await service.logout("invalid.token")


class TestAuthServicePasswordReset:
    """Test AuthService password reset flow (Requirement 2.4)."""

    @pytest.mark.asyncio
    async def test_request_password_reset_success(self):
        """Valid email should generate a reset token."""
        settings = _test_settings()
        user = _make_user()
        db = _mock_db_with_user(user)

        service = AuthService(db, settings)
        result = await service.request_password_reset("test@example.com")

        assert "reset_token" in result

    @pytest.mark.asyncio
    async def test_request_password_reset_unknown_email(self):
        """Unknown email should raise AuthenticationError."""
        settings = _test_settings()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError):
            await service.request_password_reset("unknown@example.com")

    @pytest.mark.asyncio
    async def test_reset_password_success(self):
        """Valid reset token and password should update the password."""
        settings = _test_settings()
        user = _make_user()
        db = _mock_db_with_user(user)

        reset_token = create_password_reset_token(str(user.id), settings)

        service = AuthService(db, settings)
        result = await service.reset_password(reset_token, "NewPass123")

        assert "message" in result
        # Password should have changed
        assert verify_password("NewPass123", user.password_hash, settings)

    @pytest.mark.asyncio
    async def test_reset_password_weak_password(self):
        """Weak password should raise PasswordValidationError."""
        settings = _test_settings()
        user = _make_user()
        db = _mock_db_with_user(user)

        reset_token = create_password_reset_token(str(user.id), settings)

        service = AuthService(db, settings)
        with pytest.raises(PasswordValidationError):
            await service.reset_password(reset_token, "weak")

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self):
        """Invalid reset token should raise AuthenticationError."""
        settings = _test_settings()
        db = AsyncMock()

        service = AuthService(db, settings)
        with pytest.raises(AuthenticationError):
            await service.reset_password("invalid.token", "NewPass123")

    @pytest.mark.asyncio
    async def test_reset_password_resets_lockout(self):
        """Password reset should clear lockout state."""
        settings = _test_settings()
        user = _make_user(failed_login_attempts=5)
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        db = _mock_db_with_user(user)

        reset_token = create_password_reset_token(str(user.id), settings)

        service = AuthService(db, settings)
        await service.reset_password(reset_token, "NewPass123")

        assert user.failed_login_attempts == 0
        assert user.locked_until is None
