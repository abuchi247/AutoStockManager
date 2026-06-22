"""
Inventory Movement Ledger model.

This module defines the immutable ledger tracking every stock quantity change
in the system. Each entry records a single movement (sale, purchase receipt,
transfer, adjustment, return) and references the originating transaction.

The ledger is append-only — entries are never modified or deleted. The sum of
all quantity_change values for a given (spare_part_id, location_id) pair equals
the current stock at that location.

Satisfies Requirement 4.8: THE Location_Manager SHALL maintain an
Inventory_Movement_Ledger recording every stock quantity change with source,
destination, reason, and reference.

Satisfies Requirement 18.9: THE ERP_System SHALL maintain a composite index on
the Inventory_Movement_Ledger for spare_part_id, location_id, and created_at
columns to support cache reconciliation and audit snapshot queries.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MovementType(str, enum.Enum):
    """Classification of inventory movements."""

    PURCHASE = "PURCHASE"
    SALE = "SALE"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_IN_TRANSIT = "TRANSFER_IN_TRANSIT"
    TRANSFER_RECEIVED = "TRANSFER_RECEIVED"
    ADJUSTMENT = "ADJUSTMENT"
    RETURN = "RETURN"


class ReferenceType(str, enum.Enum):
    """Type of the originating document for a ledger entry."""

    SALE = "sale"
    PURCHASE_ORDER = "purchase_order"
    GRN = "grn"
    TRANSFER = "transfer"
    AUDIT = "audit"


class InventoryMovementLedger(Base):
    """Immutable ledger entry recording a single stock movement.

    This model intentionally does NOT inherit from BaseModel (which has
    updated_at/updated_by) because ledger entries are append-only and should
    never be modified after creation. It uses its own id and created_at/created_by.

    Columns:
        id              - UUID primary key
        spare_part_id   - The spare part affected by this movement
        location_id     - The location where the movement occurred
        quantity_change  - Signed decimal: positive for inflows, negative for outflows
        movement_type   - Classification of the movement (e.g., SALE, PURCHASE,
                          TRANSFER_OUT, TRANSFER_IN, ADJUSTMENT, RETURN)
        reference_type  - Type of the originating document (e.g., "sale", "grn",
                          "transfer", "purchase_order", "audit")
        reference_id    - UUID of the originating document
        unit_cost       - Cost per unit at the time of this movement
        created_by      - UUID of the user who initiated this movement
        created_at      - Timestamp when this entry was created (immutable)

    Indexes:
        - Composite index on (spare_part_id, location_id, created_at) for
          reconciliation queries and audit snapshot filtering.
    """

    __tablename__ = "inventory_movement_ledger"

    __table_args__ = (
        Index(
            "ix_movement_ledger_part_location_created",
            "spare_part_id",
            "location_id",
            "created_at",
        ),
    )

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique identifier for this ledger entry",
    )

    # -------------------------------------------------------------------------
    # Core Movement Data
    # -------------------------------------------------------------------------
    spare_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="The spare part affected by this movement",
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="The location where the movement occurred",
    )

    quantity_change: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Signed quantity change: positive=inflow, negative=outflow",
    )

    movement_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of movement (SALE, PURCHASE, TRANSFER_OUT, TRANSFER_IN, ADJUSTMENT, RETURN)",
    )

    reference_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of the originating document (sale, purchase_order, grn, transfer, audit)",
    )

    reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="UUID of the originating document",
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=False,
        default=Decimal("0"),
        comment="Cost per unit at the time of this movement",
    )

    # -------------------------------------------------------------------------
    # Audit Fields (append-only — no updated_at/updated_by)
    # -------------------------------------------------------------------------
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="UUID of the user who initiated this movement",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp when this ledger entry was created (immutable)",
    )
