"""
Audit Trail model.

This module defines the immutable audit trail recording every critical action
performed in the ERP system. Each entry captures who performed the action,
what type of action it was, which entity was affected, and the before/after
state of the entity as structured JSON for field-level comparison.

The audit trail is APPEND-ONLY — records are never modified or deleted via the
application layer. This ensures a tamper-proof log for regulatory compliance
and forensic analysis.

Satisfies Requirements:
- 2.6: When a user performs CRUD, audit trail records user identity, action type,
       timestamp, entity, old/new values
- 15.1: Record: timestamp, user identity, action type, entity type, entity id,
        old values, new values
- 15.2: Critical events: login/logout, CRUD, approval, payment, stock adjustment
- 15.3: Retain all records for 7 years minimum
- 15.4: Store old/new values as structured data for field-level comparison
- 15.5: Support querying by user, entity_type, entity_id, action_type, date_range
- 15.6: Append-only — no user including Admin can modify or delete audit trail records
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActionType(str, enum.Enum):
    """Classification of auditable actions.

    Covers all critical events as defined in Requirement 15.2:
    login/logout, CRUD, approval, payment, stock adjustment.
    """

    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    APPROVE = "APPROVE"
    PAYMENT = "PAYMENT"
    STOCK_ADJUSTMENT = "STOCK_ADJUSTMENT"


class AuditTrail(Base):
    """Immutable audit trail entry recording a single critical action.

    This model intentionally does NOT inherit from BaseModel (which has
    updated_at/updated_by) because audit trail entries are append-only and
    must never be modified or deleted after creation (Requirement 15.6).

    Columns:
        id          - UUID primary key
        user_id     - UUID of the user who performed the action
        action_type - Type of action performed (LOGIN, LOGOUT, CREATE, etc.)
        entity_type - Type of entity affected (e.g., 'spare_part', 'sale', 'user')
        entity_id   - UUID of the affected entity (nullable for login/logout)
        old_values  - JSON snapshot of entity state before the action (nullable)
        new_values  - JSON snapshot of entity state after the action (nullable)
        ip_address  - IP address from which the action was performed
        created_at  - Timestamp when the event occurred (immutable)

    Indexes:
        - Composite index on (entity_type, entity_id) for entity-scoped queries
        - Index on user_id for user-scoped queries
        - Index on action_type for filtering by action
        - Index on created_at for date range queries
    """

    __tablename__ = "audit_trail"

    __table_args__ = (
        Index("ix_audit_trail_entity", "entity_type", "entity_id"),
        Index("ix_audit_trail_user_id", "user_id"),
        Index("ix_audit_trail_action_type", "action_type"),
        Index("ix_audit_trail_created_at", "created_at"),
    )

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique identifier for this audit trail entry",
    )

    # -------------------------------------------------------------------------
    # Core Audit Data
    # -------------------------------------------------------------------------
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="UUID of the user who performed the action",
    )

    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of action performed (LOGIN, LOGOUT, CREATE, UPDATE, DELETE, APPROVE, PAYMENT, STOCK_ADJUSTMENT)",
    )

    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Type of entity affected (e.g., 'spare_part', 'sale', 'user')",
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="UUID of the affected entity (nullable for login/logout actions)",
    )

    # -------------------------------------------------------------------------
    # State Snapshots (Requirement 15.4)
    # -------------------------------------------------------------------------
    old_values: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON snapshot of entity state before the action (for field-level comparison)",
    )

    new_values: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON snapshot of entity state after the action (for field-level comparison)",
    )

    # -------------------------------------------------------------------------
    # Request Context
    # -------------------------------------------------------------------------
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address from which the action was performed (IPv4 or IPv6)",
    )

    # -------------------------------------------------------------------------
    # Timestamp (append-only — no updated_at)
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp when this audit event was recorded (immutable)",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditTrail(id={self.id}, user_id={self.user_id}, "
            f"action_type={self.action_type}, entity_type={self.entity_type}, "
            f"entity_id={self.entity_id})>"
        )
