"""
PurchaseOrder and PurchaseOrderItem models for the Auto Spare Parts ERP system.

This module defines the PurchaseOrder and PurchaseOrderItem models which track
the lifecycle of supplier orders from draft through receipt or cancellation.

Satisfies Requirement 9.1: THE Purchase_Manager SHALL support the following
Purchase_Order states: draft, approved, ordered, partially received, received,
and cancelled.

Satisfies Requirement 9.2: WHEN a Purchase_Order is created, THE Purchase_Manager
SHALL set the initial state to draft.

Satisfies Requirement 9.8: THE Purchase_Manager SHALL track the Purchase_Order
total as the sum of line item quantities multiplied by unit costs.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.supplier import Supplier
    from app.models.spare_part import SparePart


class PurchaseOrderStatus(str, enum.Enum):
    """Enumeration of purchase order lifecycle statuses.

    Satisfies Requirement 9.1: THE Purchase_Manager SHALL support the following
    Purchase_Order states: draft, approved, ordered, partially received, received,
    and cancelled.
    """

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ORDERED = "ORDERED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class PurchaseOrder(BaseModel):
    """Purchase order model tracking supplier order lifecycle.

    Represents a purchase order issued to a supplier, following the lifecycle:
    DRAFT → APPROVED → ORDERED → PARTIALLY_RECEIVED/RECEIVED (or CANCELLED).

    Satisfies Requirement 9.1: Supports all required PO states.
    Satisfies Requirement 9.2: Initial state defaults to DRAFT.
    Satisfies Requirement 9.8: total_amount tracks the PO total.

    Columns:
        supplier_id  - FK to suppliers
        status       - Current PO lifecycle status
        total_amount - Sum of (quantity_ordered * unit_cost) for all line items
        notes        - Optional text notes for the PO
        approved_by  - FK to users who approved this PO (nullable)
        approved_at  - Timestamp of approval (nullable)

    Relationships:
        items - Collection of PurchaseOrderItem line items
    """

    __tablename__ = "purchase_orders"

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id"),
        nullable=False,
        comment="Supplier this purchase order is issued to",
    )

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus, name="purchase_order_status", create_constraint=True),
        nullable=False,
        default=PurchaseOrderStatus.DRAFT,
        comment="Current purchase order lifecycle status",
    )

    # -------------------------------------------------------------------------
    # Financial
    # -------------------------------------------------------------------------
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total PO amount: sum of (quantity_ordered * unit_cost) per item",
    )

    # -------------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------------
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional notes for this purchase order",
    )

    # -------------------------------------------------------------------------
    # Approval
    # -------------------------------------------------------------------------
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        comment="User who approved this purchase order",
    )

    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when this purchase order was approved",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    supplier: Mapped[Optional["Supplier"]] = relationship(
        "Supplier",
        lazy="selectin",
    )

    def calculate_total(self) -> Decimal:
        """Calculate the total amount from line items.

        Satisfies Requirement 9.8: THE Purchase_Manager SHALL track the
        Purchase_Order total as the sum of line item quantities multiplied
        by unit costs.

        Returns:
            Total amount as sum of (quantity_ordered * unit_cost) for all items.
        """
        return sum(
            (item.quantity_ordered * item.unit_cost for item in self.items),
            Decimal("0.00"),
        )

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrder(id={self.id}, supplier_id={self.supplier_id}, "
            f"status={self.status}, total_amount={self.total_amount})>"
        )


class PurchaseOrderItem(BaseModel):
    """Purchase order line item model.

    Represents an individual item within a purchase order, tracking the
    spare part to be purchased, ordered quantity, received quantity, and unit cost.

    Columns:
        purchase_order_id - FK to the parent purchase order
        spare_part_id     - FK to the spare part being ordered
        quantity_ordered  - Quantity requested from the supplier
        quantity_received - Quantity received so far (default 0)
        unit_cost         - Cost per unit for this line item

    Relationships:
        purchase_order - The parent purchase order
    """

    __tablename__ = "purchase_order_items"

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id"),
        nullable=False,
        comment="Parent purchase order",
    )

    spare_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spare_parts.id"),
        nullable=False,
        comment="The spare part being ordered",
    )

    # -------------------------------------------------------------------------
    # Quantities
    # -------------------------------------------------------------------------
    quantity_ordered: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        comment="Quantity ordered from the supplier",
    )

    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Quantity received so far",
    )

    # -------------------------------------------------------------------------
    # Cost
    # -------------------------------------------------------------------------
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        comment="Cost per unit for this line item",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    purchase_order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder",
        back_populates="items",
        lazy="selectin",
    )

    spare_part: Mapped[Optional["SparePart"]] = relationship(
        "SparePart",
        lazy="selectin",
    )

    @property
    def line_total(self) -> Decimal:
        """Calculate line total as quantity_ordered * unit_cost."""
        return self.quantity_ordered * self.unit_cost

    @property
    def is_fully_received(self) -> bool:
        """Check if this line item has been fully received."""
        return self.quantity_received >= self.quantity_ordered

    def __repr__(self) -> str:
        return (
            f"<PurchaseOrderItem(id={self.id}, po_id={self.purchase_order_id}, "
            f"spare_part_id={self.spare_part_id}, qty_ordered={self.quantity_ordered}, "
            f"qty_received={self.quantity_received}, unit_cost={self.unit_cost})>"
        )
