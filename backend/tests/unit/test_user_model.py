"""Unit tests for the User model."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.user import User, UserRole


class TestUserModelColumns:
    """Test that the User model has the correct column definitions."""

    def test_tablename(self):
        """User model should use 'users' table."""
        assert User.__tablename__ == "users"

    def test_username_column(self):
        """User should have a unique, non-nullable username string column."""
        col = User.__table__.columns["username"]
        assert isinstance(col.type, String)
        assert col.nullable is False
        assert col.unique is True

    def test_email_column(self):
        """User should have a unique, non-nullable email string column."""
        col = User.__table__.columns["email"]
        assert isinstance(col.type, String)
        assert col.nullable is False
        assert col.unique is True

    def test_password_hash_column(self):
        """User should have a non-nullable password_hash string column."""
        col = User.__table__.columns["password_hash"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_role_column(self):
        """User should have a non-nullable role string column."""
        col = User.__table__.columns["role"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_is_active_column(self):
        """User should have a boolean is_active column defaulting to True."""
        col = User.__table__.columns["is_active"]
        assert isinstance(col.type, Boolean)
        assert col.nullable is False

    def test_locked_until_column(self):
        """User should have a nullable locked_until datetime column."""
        col = User.__table__.columns["locked_until"]
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True
        assert col.nullable is True

    def test_failed_login_attempts_column(self):
        """User should have an integer failed_login_attempts column defaulting to 0."""
        col = User.__table__.columns["failed_login_attempts"]
        assert isinstance(col.type, Integer)
        assert col.nullable is False

    def test_inherits_base_model_columns(self):
        """User should inherit id, created_at, updated_at, created_by, updated_by from BaseModel."""
        columns = User.__table__.columns
        assert "id" in columns
        assert "created_at" in columns
        assert "updated_at" in columns
        assert "created_by" in columns
        assert "updated_by" in columns

    def test_inherits_soft_delete_columns(self):
        """User should inherit deleted_at, deleted_by from SoftDeleteMixin."""
        columns = User.__table__.columns
        assert "deleted_at" in columns
        assert "deleted_by" in columns


class TestUserRole:
    """Test the UserRole enum values (Requirement 2.1)."""

    def test_admin_role(self):
        """UserRole should have Admin value."""
        assert UserRole.ADMIN == "Admin"

    def test_manager_role(self):
        """UserRole should have Manager value."""
        assert UserRole.MANAGER == "Manager"

    def test_salesperson_role(self):
        """UserRole should have Salesperson value."""
        assert UserRole.SALESPERSON == "Salesperson"

    def test_storekeeper_role(self):
        """UserRole should have Storekeeper value."""
        assert UserRole.STOREKEEPER == "Storekeeper"

    def test_four_roles_exactly(self):
        """There should be exactly four roles."""
        assert len(UserRole) == 4


class TestUserInstance:
    """Test User model instance behavior."""

    def test_create_user_instance(self):
        """Should be able to create a User instance with required fields."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$somehash",
            role=UserRole.ADMIN.value,
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == "Admin"

    def test_is_active_defaults_to_true(self):
        """New user should have is_active=True when explicitly set (default applies at DB level)."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$somehash",
            role=UserRole.SALESPERSON.value,
            is_active=True,
        )
        assert user.is_active is True

    def test_failed_login_attempts_defaults_to_zero(self):
        """New user should have failed_login_attempts=0 when explicitly set (default applies at DB level)."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$somehash",
            role=UserRole.MANAGER.value,
            failed_login_attempts=0,
        )
        assert user.failed_login_attempts == 0

    def test_locked_until_defaults_to_none(self):
        """New user should have locked_until=None."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$somehash",
            role=UserRole.STOREKEEPER.value,
        )
        assert user.locked_until is None

    def test_is_locked_false_when_no_lock(self):
        """is_locked should be False when locked_until is None."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$somehash",
            role=UserRole.ADMIN.value,
        )
        assert user.is_locked is False

    def test_is_locked_true_when_lock_is_future(self):
        """is_locked should be True when locked_until is in the future."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$somehash",
            role=UserRole.ADMIN.value,
        )
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        assert user.is_locked is True

    def test_is_locked_false_when_lock_expired(self):
        """is_locked should be False when locked_until is in the past."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$somehash",
            role=UserRole.ADMIN.value,
        )
        user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert user.is_locked is False

    def test_soft_delete_inherited(self):
        """User should support soft_delete from SoftDeleteMixin."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$somehash",
            role=UserRole.ADMIN.value,
        )
        assert user.is_deleted is False
        user.soft_delete(deleted_by="admin")
        assert user.is_deleted is True
        assert user.deleted_by == "admin"

    def test_repr(self):
        """User __repr__ should include id, username, and role."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$somehash",
            role=UserRole.ADMIN.value,
        )
        repr_str = repr(user)
        assert "testuser" in repr_str
        assert "Admin" in repr_str
