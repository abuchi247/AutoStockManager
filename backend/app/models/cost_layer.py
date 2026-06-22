"""
Cost Layer model for FIFO inventory valuation.

This module defines the CostLayer model which tracks inventory cost per batch
at each location. Cost layers are consumed in chronological order (FIFO) when
stock is sold or transferred out.

Satisfies:
- Requirement 1.8: Maintain Cost_Layers per Spare_Part per location with
  unit cost, original quantity, and remaining unconsumed quantity.
- Requirement 1.10: Consume quantities from Cost_Layers in chronological
  order of receipt date starting with the oldest layer with remaining quantity.
- Requirement 18.10: Partial composite index on cost_layers for FIFO queries.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class CostLayer(BaseModel):
    """Cost layer representing a batch of inventory at a specific cost.

    Each CostLayer records a quantity of a spare part received at a specific
    unit cost at a particular location. When stock is consumed (via sales or
    transfers), layers are depleted in FIFO order — oldest first.

    Satisfies Requirement 1.8: THE ERP_System SHALL maintain Cost_Layers per
    Spare_Part per location, where each Cost_Layer records the unit cost,
    original quantity received, and remaining unconsumed quantity.

    Columns:
        spare_part_id        - FK to the spare part this layer belongs to
        location_id          - FK to the location where this layer exists
        unit_cost            - Cost per unit for this batch
        original_quantity    - Quantity originally received in this layer
        remaining_quantity   - Quantity still available for consumption
        source_type          - Origin of this layer (e.g., 'purchase', 'transfer', 'return')
        source_reference_id  - FK/reference to the source document (GRN, transfer, etc.)
    """

    __tablename__ = "cost_layers"

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    spare_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spare_parts.id"),
        nullable=False,
        comment="Spare part this cost layer belongs to",
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id"),
        nullable=False,
        comment="Location where this cost layer exists",
    )

    # -------------------------------------------------------------------------
    # Cost and Quantity
    # -------------------------------------------------------------------------
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=False,
        comment="Cost per unit for this batch",
    )

    original_quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=False,
        comment="Quantity originally received in this layer",
    )

    remaining_quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=False,
        comment="Quantity still available for FIFO consumption",
    )

    # -------------------------------------------------------------------------
    # Source Tracking
    # -------------------------------------------------------------------------
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Origin type: purchase, transfer, return, adjustment",
    )

    source_reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Reference to the source document (GRN ID, transfer ID, etc.)",
    )

    # -------------------------------------------------------------------------
    # Indexes
    # -------------------------------------------------------------------------
    __table_args__ = (
        # Partial composite index for FIFO queries: only layers with remaining stock.
        # This enables efficient lookup of consumable layers ordered by created_at.
        # Satisfies Requirement 18.10.
        Index(
            "ix_cost_layers_fifo_lookup",
            "spare_part_id",
            "location_id",
            "created_at",
            postgresql_where="remaining_quantity > 0",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CostLayer(id={self.id}, spare_part_id={self.spare_part_id}, "
            f"location_id={self.location_id}, unit_cost={self.unit_cost}, "
            f"remaining={self.remaining_quantity}/{self.original_quantity})>"
        )
