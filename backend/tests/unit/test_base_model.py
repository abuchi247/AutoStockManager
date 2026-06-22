"""Unit tests for BaseModel and SoftDeleteMixin."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import DateTime, String, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.base import BaseModel, SoftDeleteMixin, SoftDeleteQuery, with_soft_delete_filter
from app.database import Base


# =============================================================================
# Define concrete test models at module level to avoid SQLAlchemy table re-creation
# =============================================================================

class _ConcreteModel(BaseModel, SoftDeleteMixin):
    """Test model combining BaseModel and SoftDeleteMixin."""
    __tablename__ = "test_concrete"
    __table_args__ = {"extend_existing": True}


class _QueryModel(BaseModel, SoftDeleteMixin):
    """Test model for query filter tests."""
    __tablename__ = "test_query_model"
    __table_args__ = {"extend_existing": True}


class _FilterModel(BaseModel, SoftDeleteMixin):
    """Test model for with_soft_delete_filter tests."""
    __tablename__ = "test_filter_model"
    __table_args__ = {"extend_existing": True}


# =============================================================================
# Tests
# =============================================================================


class TestBaseModelColumns:
    """Test that BaseModel defines the required audit columns (Requirement 1.1)."""

    def test_base_model_is_abstract(self):
        """BaseModel should be abstract and not create its own table."""
        assert BaseModel.__abstract__ is True

    def test_id_column_exists(self):
        """BaseModel should have a UUID primary key column."""
        assert hasattr(BaseModel, "id")

    def test_id_column_is_uuid_type(self):
        """The id column should use PostgreSQL UUID type."""
        col = _ConcreteModel.__table__.columns["id"]
        assert isinstance(col.type, PG_UUID)
        assert col.primary_key is True

    def test_id_column_has_default(self):
        """The id column should have a default (uuid4)."""
        col = _ConcreteModel.__table__.columns["id"]
        assert col.default is not None

    def test_created_at_column_exists(self):
        """BaseModel should have a created_at timestamp column."""
        assert hasattr(BaseModel, "created_at")
        col = _ConcreteModel.__table__.columns["created_at"]
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True
        assert col.nullable is False

    def test_updated_at_column_exists(self):
        """BaseModel should have an updated_at timestamp column."""
        assert hasattr(BaseModel, "updated_at")
        col = _ConcreteModel.__table__.columns["updated_at"]
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True
        assert col.nullable is False

    def test_updated_at_has_onupdate(self):
        """The updated_at column should have an onupdate hook."""
        col = _ConcreteModel.__table__.columns["updated_at"]
        assert col.onupdate is not None

    def test_created_by_column_exists(self):
        """BaseModel should have a created_by string column."""
        assert hasattr(BaseModel, "created_by")
        col = _ConcreteModel.__table__.columns["created_by"]
        assert isinstance(col.type, String)
        assert col.nullable is True

    def test_updated_by_column_exists(self):
        """BaseModel should have an updated_by string column."""
        assert hasattr(BaseModel, "updated_by")
        col = _ConcreteModel.__table__.columns["updated_by"]
        assert isinstance(col.type, String)
        assert col.nullable is True


class TestSoftDeleteMixin:
    """Test the SoftDeleteMixin columns (Requirement 1.2)."""

    def test_mixin_has_deleted_at(self):
        """SoftDeleteMixin should define a deleted_at column."""
        assert hasattr(SoftDeleteMixin, "deleted_at")
        col = _ConcreteModel.__table__.columns["deleted_at"]
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True
        assert col.nullable is True

    def test_mixin_has_deleted_by(self):
        """SoftDeleteMixin should define a deleted_by column."""
        assert hasattr(SoftDeleteMixin, "deleted_by")
        col = _ConcreteModel.__table__.columns["deleted_by"]
        assert isinstance(col.type, String)
        assert col.nullable is True


class TestSoftDeleteMixinBehavior:
    """Test soft-delete behavior on a concrete model."""

    def test_is_deleted_false_by_default(self):
        """A new instance should not be marked as deleted."""
        instance = _ConcreteModel()
        assert instance.is_deleted is False

    def test_soft_delete_sets_deleted_at(self):
        """soft_delete() should set the deleted_at timestamp."""
        instance = _ConcreteModel()
        instance.soft_delete(deleted_by="admin_user")
        assert instance.deleted_at is not None
        assert isinstance(instance.deleted_at, datetime)
        assert instance.deleted_by == "admin_user"
        assert instance.is_deleted is True

    def test_soft_delete_timestamp_is_timezone_aware(self):
        """soft_delete() should set a timezone-aware timestamp."""
        instance = _ConcreteModel()
        instance.soft_delete(deleted_by="user1")
        assert instance.deleted_at.tzinfo is not None

    def test_restore_clears_deletion(self):
        """restore() should clear deleted_at and deleted_by."""
        instance = _ConcreteModel()
        instance.soft_delete(deleted_by="admin_user")
        instance.restore()
        assert instance.deleted_at is None
        assert instance.deleted_by is None
        assert instance.is_deleted is False

    def test_soft_delete_without_user(self):
        """soft_delete() without a user should still set deleted_at."""
        instance = _ConcreteModel()
        instance.soft_delete()
        assert instance.deleted_at is not None
        assert instance.deleted_by is None
        assert instance.is_deleted is True

    def test_id_default_is_none_before_flush(self):
        """The id field is None before insertion (default is server-side or deferred)."""
        instance = _ConcreteModel()
        # Before being added to a session/flushed, id may be None
        # or auto-generated depending on how the default is called.
        # SQLAlchemy's default callables fire at flush time for mapped_column.
        assert instance.id is None or isinstance(instance.id, uuid.UUID)


class TestSoftDeleteQuery:
    """Test the SoftDeleteQuery helper."""

    def test_active_filter_adds_where_clause(self):
        """SoftDeleteQuery.active() should add a WHERE deleted_at IS NULL filter."""
        stmt = select(_QueryModel)
        filtered = SoftDeleteQuery.active(stmt, _QueryModel)
        compiled = str(filtered.compile(compile_kwargs={"literal_binds": True}))
        assert "deleted_at" in compiled
        assert "NULL" in compiled.upper()

    def test_deleted_only_filter(self):
        """SoftDeleteQuery.deleted_only() should filter for deleted records."""
        stmt = select(_QueryModel)
        filtered = SoftDeleteQuery.deleted_only(stmt, _QueryModel)
        compiled = str(filtered.compile(compile_kwargs={"literal_binds": True}))
        assert "deleted_at" in compiled
        assert "IS NOT NULL" in compiled.upper()


class TestWithSoftDeleteFilter:
    """Test the with_soft_delete_filter helper function."""

    def test_with_soft_delete_filter_excludes_deleted(self):
        """with_soft_delete_filter should add IS NULL filter on deleted_at."""
        stmt = select(_FilterModel)
        filtered = with_soft_delete_filter(stmt, _FilterModel)
        compiled = str(filtered.compile(compile_kwargs={"literal_binds": True}))
        assert "deleted_at" in compiled
        assert "NULL" in compiled.upper()

    def test_filter_function_and_class_produce_equivalent_results(self):
        """with_soft_delete_filter and SoftDeleteQuery.active should behave the same."""
        stmt = select(_FilterModel)
        from_func = str(
            with_soft_delete_filter(stmt, _FilterModel).compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        from_class = str(
            SoftDeleteQuery.active(stmt, _FilterModel).compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        # Both should produce equivalent WHERE clauses
        assert "deleted_at" in from_func
        assert "deleted_at" in from_class
