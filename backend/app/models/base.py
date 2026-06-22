"""
Base model module with audit columns and soft-delete mixin.

This module defines the foundational model classes that all other database models
inherit from. It establishes two key patterns used throughout the ERP system:

1. BaseModel - An abstract SQLAlchemy model providing:
   - UUID primary keys for globally unique record identification
   - Audit columns (created_at, updated_at, created_by, updated_by) on every table
   - Satisfies Requirement 1.1: Every database table includes id, created_at,
     updated_at, created_by, and updated_by columns

2. SoftDeleteMixin - A mixin class for financial/important records providing:
   - Soft-delete columns (deleted_at, deleted_by) instead of physical deletion
   - Helper methods to mark records as deleted and restore them
   - Satisfies Requirement 1.2: Financial records are soft-deleted by setting
     a deleted_at timestamp and deleted_by user reference

3. Query filtering utilities - Helper functions and classes that make it easy
   to exclude soft-deleted records from queries by default, while still allowing
   access to deleted records when needed (e.g., for audit trails).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, declared_attr

from app.database import Base


# =============================================================================
# BaseModel - Abstract base with audit columns for all tables
# =============================================================================


class BaseModel(Base):
    """Abstract base model with UUID primary key and audit columns.

    All domain models in the ERP system inherit from this class to ensure
    consistent record identification and audit tracking across every table.

    Columns provided:
        id         - UUID v4 primary key, auto-generated for each new record
        created_at - Timestamp when the record was first created (timezone-aware)
        updated_at - Timestamp of the last modification (auto-updated on change)
        created_by - Identifier (username or user ID) of who created the record
        updated_by - Identifier (username or user ID) of who last modified the record

    This satisfies Requirement 1.1: THE ERP_System SHALL include id, created_at,
    updated_at, created_by, and updated_by columns on every database table.

    Usage:
        class SparePart(BaseModel):
            __tablename__ = "spare_parts"
            name: Mapped[str] = mapped_column(String(255))
    """

    # Mark as abstract so SQLAlchemy does not create a table for BaseModel itself.
    # Only concrete subclasses will produce actual database tables.
    __abstract__ = True

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    # UUID v4 provides globally unique identifiers without sequential exposure.
    # This prevents enumeration attacks and allows distributed ID generation.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique identifier for the record (UUID v4)",
    )

    # -------------------------------------------------------------------------
    # Audit Timestamps
    # -------------------------------------------------------------------------
    # created_at is set once when the record is inserted.
    # All timestamps are timezone-aware (stored as UTC) for consistency
    # across different server/client timezones.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp when this record was created",
    )

    # updated_at is automatically refreshed on every UPDATE via SQLAlchemy's
    # onupdate hook. This ensures we always know when a record last changed.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp of the last update to this record",
    )

    # -------------------------------------------------------------------------
    # Audit User References
    # -------------------------------------------------------------------------
    # These columns track WHO created/modified the record. They store a user
    # identifier string (typically the user's UUID or username). Nullable because
    # system-initiated operations (migrations, seeds) may not have a user context.
    created_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User identifier of who created this record",
    )

    updated_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User identifier of who last updated this record",
    )


# =============================================================================
# SoftDeleteMixin - Soft deletion support for financial/important records
# =============================================================================


class SoftDeleteMixin:
    """Mixin that adds soft-delete capability to a model.

    Instead of physically removing financial and important records from the
    database, this mixin marks them as deleted by recording:
    - deleted_at: The timestamp when deletion occurred
    - deleted_by: The user who performed the deletion

    This preserves data for audit trails, regulatory compliance, and potential
    restoration. The record remains in the database but is excluded from normal
    queries via filtering helpers.

    Satisfies Requirement 1.2: WHEN a financial record is deleted,
    THE ERP_System SHALL perform a Soft_Delete by setting a deleted_at timestamp
    and deleted_by user reference instead of physically removing the record.

    Usage:
        class SparePart(BaseModel, SoftDeleteMixin):
            __tablename__ = "spare_parts"
            name: Mapped[str] = mapped_column(String(255))

        # Mark a record as deleted
        part.soft_delete(deleted_by="user-123")

        # Check if deleted
        if part.is_deleted:
            ...

        # Restore a soft-deleted record
        part.restore()
    """

    # -------------------------------------------------------------------------
    # Soft-Delete Columns
    # -------------------------------------------------------------------------
    # deleted_at is None for active records and set to a timestamp for deleted ones.
    # This column is the primary indicator of soft-deletion status.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp when this record was soft-deleted (NULL means active)",
    )

    # deleted_by records which user performed the soft-delete action.
    # This is important for audit and accountability purposes.
    deleted_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        comment="User identifier of who soft-deleted this record",
    )

    # -------------------------------------------------------------------------
    # Convenience Properties and Methods
    # -------------------------------------------------------------------------

    @property
    def is_deleted(self) -> bool:
        """Check whether this record has been soft-deleted.

        Returns:
            True if the record has a deleted_at timestamp set, False otherwise.
        """
        return self.deleted_at is not None

    def soft_delete(self, deleted_by: Optional[str] = None) -> None:
        """Mark this record as soft-deleted.

        Sets the deleted_at timestamp to the current UTC time and records
        which user performed the deletion. The record remains in the database
        but will be excluded from standard queries.

        Args:
            deleted_by: The identifier of the user performing the deletion.
                        Can be a username, user UUID string, or None for
                        system-initiated deletions.
        """
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by

    def restore(self) -> None:
        """Restore a previously soft-deleted record.

        Clears both deleted_at and deleted_by, making the record appear
        as an active (non-deleted) record in filtered queries again.
        """
        self.deleted_at = None
        self.deleted_by = None

    @declared_attr
    @classmethod
    def __mapper_args__(cls) -> dict[str, Any]:
        """Mapper arguments hook for soft-delete models.

        This declared_attr allows subclasses to customize mapper behavior.
        Currently returns an empty dict but provides an extension point for
        future enhancements like polymorphic identity or default ordering.
        """
        return {}


# =============================================================================
# Query Filtering Utilities
# =============================================================================
# These utilities provide a consistent way to filter out soft-deleted records
# from database queries. They implement the requirement that soft-deleted
# records should be excluded by default from normal application queries.


def with_soft_delete_filter(query: Any, model: Any) -> Any:
    """Apply a soft-delete filter to exclude deleted records from a query.

    This is the simplest way to ensure a query only returns active (non-deleted)
    records. It adds a WHERE clause checking that deleted_at IS NULL.

    Args:
        query: A SQLAlchemy select statement (e.g., select(MyModel)).
        model: The model class that includes SoftDeleteMixin. Must have
               a deleted_at column.

    Returns:
        The query with an additional filter excluding soft-deleted records.

    Example:
        # Build a query that only returns active spare parts
        stmt = with_soft_delete_filter(select(SparePart), SparePart)
        result = await session.execute(stmt)
        active_parts = result.scalars().all()
    """
    return query.filter(model.deleted_at.is_(None))


class SoftDeleteQuery:
    """Helper class providing static methods for soft-delete-aware querying.

    Provides three query patterns:
    1. active()       - Returns only non-deleted records (most common)
    2. deleted_only() - Returns only soft-deleted records (for admin views)
    3. No filter      - Returns all records (use plain select() without this helper)

    This class does not need to be instantiated — all methods are static.

    Example:
        # Get only active (non-deleted) records
        stmt = SoftDeleteQuery.active(select(SparePart), SparePart)

        # Get only soft-deleted records (e.g., for a "trash" view)
        stmt = SoftDeleteQuery.deleted_only(select(SparePart), SparePart)

        # Get all records including deleted (no filtering)
        stmt = select(SparePart)
    """

    @staticmethod
    def active(query: Any, model: Any) -> Any:
        """Filter query to return only active (non-deleted) records.

        Adds a WHERE deleted_at IS NULL clause to exclude any records
        that have been soft-deleted.

        Args:
            query: A SQLAlchemy select statement.
            model: The model class with SoftDeleteMixin.

        Returns:
            Filtered query excluding soft-deleted records.
        """
        return query.filter(model.deleted_at.is_(None))

    @staticmethod
    def deleted_only(query: Any, model: Any) -> Any:
        """Filter query to return only soft-deleted records.

        Adds a WHERE deleted_at IS NOT NULL clause to include only
        records that have been marked as deleted.

        Useful for administrative views showing deleted records,
        recovery interfaces, or audit reporting.

        Args:
            query: A SQLAlchemy select statement.
            model: The model class with SoftDeleteMixin.

        Returns:
            Filtered query including only soft-deleted records.
        """
        return query.filter(model.deleted_at.isnot(None))
