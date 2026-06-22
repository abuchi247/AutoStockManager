"""
Transfer model for inter-location stock transfers.

This module defines the Transfer model representing the movement of spare parts
between locations (warehouses and retail branches). Transfers follow a state machine
lifecycle: pending → approved → in_transit → received (or cancelled at any point
before receipt).

Satisfies Requirement 4.2: THE Location_Manager SHALL allow users to create
Stock Transfer requests specifying spare part, quantity, source location,
and destination location.

Satisfies Requirement 4.4: THE Location_Manager SHALL enforce a transfer
approval workflow requiring manager authorization before stock movement occurs.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TransferStatus(str, enum.Enum):
    """Transfer lifecycle states.

    State transitions:
        PENDING → APPROVED → IN_TRANSIT → RECEIVED
        PENDING → CANCELLED
        APPROVED → CANCELLED
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


# Valid state transitions mapping
VALID_TRANSFER_TRANSITIONS: dict[TransferStatus, list[TransferStatus]] = {
    TransferStatus.PENDING: [TransferStatus.APPROVED, TransferStatus.CANCELLED],
    TransferStatus.APPROVED: [TransferStatus.IN_TRANSIT, TransferStatus.CANCELLED],
    TransferStatus.IN_TRANSIT: [TransferStatus.RECEIVED],
    TransferStatus.RECEIVED: [],
    TransferStatus.CANCELLED: [],
}


class Transfer(BaseModel):
    """Model representing an inter-location stock transfer.

    A transfer tracks the movement of a spare part from a source location to a
    destination location. It stores the quantity being transferred, the current
    state of the transfer, and details about FIFO cost layers consumed during
    the approval process.

    State Machine:
        - PENDING: Transfer requested, awaiting manager approval
        - APPROVED: Manager approved, FIFO layers consumed at source
        - IN_TRANSIT: Stock deducted from source, in transit to destination
        - RECEIVED: Stock received at destination, new cost layers created
        - CANCELLED: Transfer cancelled (possible from PENDING or APPROVED states)

    Columns (in addition to BaseModel audit columns):
        spare_part_id           - FK to the spare part being transferred
        source_location_id      - FK to the source location
        destination_location_id - FK to the destination location
        quantity                - Quantity being transferred
        status                  - Current transfer state (TransferStatus enum)
        consumed_layer_details  - JSON storing FIFO layer consumption details
        requested_by            - FK to the user who requested the transfer
        approved_by             - FK to the user who approved the transfer
        received_by             - FK to the user who received the transfer
        approved_at             - Timestamp when transfer was approved
        received_at             - Timestamp when transfer was received
        cancellation_reason     - Reason for cancellation (if cancelled)
    """

    __tablename__ = "transfers"

    __table_args__ = (
        Index(
            "ix_transfers_status",
            "status",
        ),
        Index(
            "ix_transfers_source_location",
            "source_location_id",
            "status",
        ),
        Index(
            "ix_transfers_destination_location",
            "destination_location_id",
            "status",
        ),
    )

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    spare_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spare_parts.id"),
        nullable=False,
        comment="Spare part being transferred",
    )

    source_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id"),
        nullable=False,
        comment="Location where stock is being transferred from",
    )

    destination_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id"),
        nullable=False,
        comment="Location where stock is being transferred to",
    )

    # -------------------------------------------------------------------------
    # Transfer Data
    # -------------------------------------------------------------------------
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=4),
        nullable=False,
        comment="Quantity of spare part being transferred",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TransferStatus.PENDING.value,
        comment="Current transfer state: PENDING, APPROVED, IN_TRANSIT, RECEIVED, CANCELLED",
    )

    consumed_layer_details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="JSON details of FIFO cost layers consumed during approval",
    )

    # -------------------------------------------------------------------------
    # User References (as UUID FKs to users table)
    # -------------------------------------------------------------------------
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="User who requested the transfer",
    )

    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        default=None,
        comment="User who approved the transfer",
    )

    received_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        default=None,
        comment="User who received the transfer at destination",
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp when the transfer was approved",
    )

    received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp when the transfer was received at destination",
    )

    # -------------------------------------------------------------------------
    # Cancellation
    # -------------------------------------------------------------------------
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="Reason for cancellation (populated when status is CANCELLED)",
    )

    def __repr__(self) -> str:
        return (
            f"<Transfer(id={self.id}, spare_part_id={self.spare_part_id}, "
            f"source={self.source_location_id}, dest={self.destination_location_id}, "
            f"qty={self.quantity}, status={self.status})>"
        )
