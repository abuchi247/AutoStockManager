"""Pydantic schemas for Goods Receipt Note (GRN) endpoints.

Defines response models for GRN data returned by the purchase order
receive endpoint.

Satisfies Requirements: 9.4, 9.5
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Response Schemas
# =============================================================================


class GRNItemResponse(BaseModel):
    """Response schema for a single GRN line item."""

    id: UUID = Field(..., description="GRN item UUID")
    grn_id: UUID = Field(..., description="Parent GRN UUID")
    po_item_id: UUID = Field(..., description="PO item UUID this receipt is for")
    spare_part_id: UUID = Field(..., description="Spare part UUID")
    quantity_received: Decimal = Field(..., description="Quantity received")
    unit_cost: Decimal = Field(..., description="Unit cost for this receipt")
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")

    model_config = {"from_attributes": True}


class GRNResponse(BaseModel):
    """Response body for a Goods Receipt Note."""

    id: UUID = Field(..., description="GRN UUID")
    purchase_order_id: UUID = Field(..., description="Parent purchase order UUID")
    location_id: UUID = Field(..., description="Receiving location UUID")
    received_by: UUID = Field(..., description="User who received the goods")
    received_at: datetime = Field(..., description="Receipt timestamp")
    notes: Optional[str] = Field(default=None, description="Receipt notes")
    items: list[GRNItemResponse] = Field(
        default_factory=list, description="GRN line items"
    )
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")

    model_config = {"from_attributes": True}


class GRNListResponse(BaseModel):
    """Response body for GRN list."""

    data: list[GRNResponse] = Field(..., description="List of GRNs")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )
