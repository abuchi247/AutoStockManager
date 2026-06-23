"""
Goods Receipt Note (GRN) model.

This module defines the GoodsReceiptNote model which records the receipt
of goods against a purchase order. Each GRN represents a single receiving
event at a specific location.

Satisfies Requirement 9.4: WHEN goods are received from a supplier,
THE Purchase_Manager SHALL create a Goods_Receipt_Note recording received
quantities per line item.

Satisfies Requirement 9.5: WHEN a Goods_Receipt_Note is confirmed,
THE Purchase_Manager SHALL add received quantities to the designated
location via the Inventory_Movement_Ledger.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class GoodsReceiptNote(BaseModel):
    """Goods Receipt Note recording a single receipt event for a purchase order.

    A GRN is created when goods arrive from a supplier. It references the
    parent purchase order and records which location received the goods.
    Individual line items are tracked via GRNItem.

    Columns:
        purchase_order_id - FK to the parent purchase order
        location_id       - FK to the location where goods were received
        received_by       - FK to the user who received the goods
        received_at       - Timestamp when goods were received
        notes             - Optional notes about the receipt

    Relationships:
        items - Collection of GRNItem line items
    """

    __tablename__ = "goods_receipt_notes"

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id"),
        nullable=False,
        comment="Parent purchase order for this goods receipt",
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id"),
        nullable=False,
        comment="Location where goods were received",
    )

    received_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="User who received the goods",
    )

    # -------------------------------------------------------------------------
    # Receipt Data
    # -------------------------------------------------------------------------
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp when goods were physically received",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional notes about this goods receipt",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    items: Mapped[list["GRNItem"]] = relationship(
        "GRNItem",
        back_populates="grn",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<GoodsReceiptNote(id={self.id}, po_id={self.purchase_order_id}, "
            f"location_id={self.location_id}, received_at={self.received_at})>"
        )
