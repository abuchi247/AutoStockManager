"""
Audit models for snapshot-based inventory auditing.

This module defines three models that support the snapshot-based audit pattern:

1. AuditSession - The audit session entity tracking type, status, and timing
2. AuditSnapshotItem - Frozen stock quantities captured at audit initiation
3. AuditCount - Physical counts submitted by users with variance calculations

The snapshot-based audit design ensures that stock movements occurring after
the audit is initiated do not affect variance calculations, providing accurate
and isolated audit results.

Satisfies Requirement 11.1: THE Audit_Module SHALL support two audit types:
Cycle_Count (subset of parts) and Full_Stock_Count (all parts at a location).

Satisfies Requirement 11.2: WHEN an audit is initiated, THE Audit_Module SHALL
create a session recording audit_type, location, date, and assigned users.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


# =============================================================================
# Enumerations
# =============================================================================


class AuditType(str, enum.Enum):
    """Enumeration of audit types.

    Satisfies Requirement 11.1: Support for Cycle_Count (subset) and
    Full_Stock_Count (all parts at a location).
    """

    CYCLE_COUNT = "CYCLE_COUNT"
    FULL_STOCK_COUNT = "FULL_STOCK_COUNT"


class AuditStatus(str, enum.Enum):
    """Enumeration of audit session lifecycle statuses.

    State transitions:
        INITIATED → IN_PROGRESS → COMPLETED
        INITIATED → CANCELLED
        IN_PROGRESS → CANCELLED
    """

    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# =============================================================================
# AuditSession Model
# =============================================================================


class AuditSession(BaseModel):
    """Audit session model representing a stock-taking event.

    An audit session captures the context for a physical inventory count,
    including which location is being audited, the type of audit, and a
    snapshot timestamp that freezes the baseline for variance calculations.

    Satisfies Requirement 11.1: Support two audit types (cycle_count, full_stock_count).
    Satisfies Requirement 11.2: Create session recording audit_type, location, date,
    and assigned users.

    Columns (in addition to BaseModel audit columns):
        location_id         - FK to the location being audited
        audit_type          - Type of audit (CYCLE_COUNT or FULL_STOCK_COUNT)
        status              - Current session status (INITIATED, IN_PROGRESS, COMPLETED, CANCELLED)
        snapshot_timestamp  - Timestamp when stock quantities were frozen for the audit
        initiated_by        - FK to the user who initiated the audit
        approved_by         - FK to the user who approved/completed the audit
        completed_at        - Timestamp when the audit was completed

    Relationships:
        snapshot_items - Collection of frozen stock quantities at audit initiation
        counts         - Collection of physical counts submitted during the audit
    """

    __tablename__ = "audit_sessions"

    __table_args__ = (
        Index(
            "ix_audit_sessions_location_status",
            "location_id",
            "status",
        ),
        Index(
            "ix_audit_sessions_status",
            "status",
        ),
    )

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id"),
        nullable=False,
        comment="Location being audited",
    )

    # -------------------------------------------------------------------------
    # Audit Classification
    # -------------------------------------------------------------------------
    audit_type: Mapped[AuditType] = mapped_column(
        Enum(AuditType, name="audit_type", create_constraint=True),
        nullable=False,
        comment="Type of audit: CYCLE_COUNT (subset) or FULL_STOCK_COUNT (all parts)",
    )

    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus, name="audit_status", create_constraint=True),
        nullable=False,
        default=AuditStatus.INITIATED,
        comment="Current audit session status",
    )

    # -------------------------------------------------------------------------
    # Snapshot and Timing
    # -------------------------------------------------------------------------
    snapshot_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when stock quantities were frozen for this audit",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp when the audit was completed/approved",
    )

    # -------------------------------------------------------------------------
    # User References
    # -------------------------------------------------------------------------
    initiated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="User who initiated the audit session",
    )

    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        default=None,
        comment="User who approved/completed the audit",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    snapshot_items: Mapped[list["AuditSnapshotItem"]] = relationship(
        "AuditSnapshotItem",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    counts: Mapped[list["AuditCount"]] = relationship(
        "AuditCount",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditSession(id={self.id}, location_id={self.location_id}, "
            f"audit_type={self.audit_type}, status={self.status})>"
        )


# =============================================================================
# AuditSnapshotItem Model
# =============================================================================


class AuditSnapshotItem(BaseModel):
    """Frozen stock quantity captured at audit initiation.

    When an audit session is initiated, the current stock quantities from
    Stock_Status_Cache are captured into snapshot items. These frozen values
    serve as the baseline for variance calculations, ensuring that stock
    movements after the audit initiation do not affect the audit results.

    Columns (in addition to BaseModel audit columns):
        session_id        - FK to the parent audit session
        spare_part_id     - FK to the spare part whose stock was captured
        snapshot_quantity - The frozen stock quantity at audit initiation time
    """

    __tablename__ = "audit_snapshot_items"

    __table_args__ = (
        Index(
            "ix_audit_snapshot_items_session_part",
            "session_id",
            "spare_part_id",
            unique=True,
        ),
    )

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_sessions.id"),
        nullable=False,
        comment="Parent audit session",
    )

    spare_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spare_parts.id"),
        nullable=False,
        comment="Spare part whose stock quantity was captured",
    )

    # -------------------------------------------------------------------------
    # Snapshot Data
    # -------------------------------------------------------------------------
    snapshot_quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Frozen stock quantity at the time of audit initiation",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    session: Mapped["AuditSession"] = relationship(
        "AuditSession",
        back_populates="snapshot_items",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditSnapshotItem(id={self.id}, session_id={self.session_id}, "
            f"spare_part_id={self.spare_part_id}, snapshot_quantity={self.snapshot_quantity})>"
        )


# =============================================================================
# AuditCount Model
# =============================================================================


class AuditCount(BaseModel):
    """Physical count submitted during an audit session.

    Records the actual physical count of a spare part at a location during
    an audit. The variance is calculated as: counted_quantity - snapshot_quantity.

    Columns (in addition to BaseModel audit columns):
        session_id       - FK to the parent audit session
        spare_part_id    - FK to the spare part being counted
        counted_quantity - The actual physical count submitted
        variance         - Difference: counted_quantity - snapshot_quantity
        counted_by       - FK to the user who performed the physical count
        counted_at       - Timestamp when the count was submitted
    """

    __tablename__ = "audit_counts"

    __table_args__ = (
        Index(
            "ix_audit_counts_session_part",
            "session_id",
            "spare_part_id",
        ),
        Index(
            "ix_audit_counts_session_id",
            "session_id",
        ),
    )

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_sessions.id"),
        nullable=False,
        comment="Parent audit session",
    )

    spare_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spare_parts.id"),
        nullable=False,
        comment="Spare part being counted",
    )

    # -------------------------------------------------------------------------
    # Count Data
    # -------------------------------------------------------------------------
    counted_quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Actual physical count quantity",
    )

    variance: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=False,
        default=Decimal("0"),
        comment="Variance: counted_quantity - snapshot_quantity",
    )

    # -------------------------------------------------------------------------
    # User and Timing
    # -------------------------------------------------------------------------
    counted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="User who performed the physical count",
    )

    counted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the count was submitted",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    session: Mapped["AuditSession"] = relationship(
        "AuditSession",
        back_populates="counts",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditCount(id={self.id}, session_id={self.session_id}, "
            f"spare_part_id={self.spare_part_id}, counted_quantity={self.counted_quantity}, "
            f"variance={self.variance})>"
        )
