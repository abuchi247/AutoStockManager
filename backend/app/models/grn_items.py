"""
GRN Item model.

This module defines the GRNItem model which records individual line items
within a Goods Receipt Note. Each GRNItem tracks the quantity received
for a specific purchase order line item.

Satisfies Requirement 9.4: WHEN goods are received from a supplier,
THE Purchase_Manager SHALL create a Goods_Receipt_Note recording received
quantities per line item.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class GRNItem(BaseModel):
    """Individual line item within a Goods Receipt Note.

    Each GRNItem records the quantity received for a specific PO line item
    and spare part. The unit_cost may differ from the PO if negotiated at
    receipt time, but typically mirrors the PO line item's unit_cost.

    Columns:
        grn_id            - FK to the parent GoodsReceiptNote
        po_item_id        - FK to the PurchaseOrderItem this receipt is for
        spare_part_id     - FK to the spare part received
        quantity_received - Quantity actually received
        unit_cost         - Cost per unit for this receipt (from PO or adjusted)

    Relationships:
        grn - The parent GoodsReceiptNote
    """

    __tablename__ = "grn_items"

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    grn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("goods_receipt_notes.id"),
        nullable=False,
        comment="Parent goods receipt note",
    )

    po_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_order_items.id"),
        nullable=False,
        comment="Purchase order line item this receipt is for",
    )

    spare_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spare_parts.id"),
        nullable=False,
        comment="The spare part received",
    )

    # -------------------------------------------------------------------------
    # Quantities and Cost
    # -------------------------------------------------------------------------
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
        comment="Quantity actually received in this GRN line",
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=False,
        comment="Cost per unit for this receipt",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    grn: Mapped["GoodsReceiptNote"] = relationship(
        "GoodsReceiptNote",
        back_populates="items",
        lazy="selectin",
    )

    @property
    def line_total(self) -> Decimal:
        """Calculate line total as quantity_received * unit_cost."""
        return self.quantity_received * self.unit_cost

    def __repr__(self) -> str:
        return (
            f"<GRNItem(id={self.id}, grn_id={self.grn_id}, "
            f"spare_part_id={self.spare_part_id}, "
            f"qty_received={self.quantity_received}, unit_cost={self.unit_cost})>"
        )
