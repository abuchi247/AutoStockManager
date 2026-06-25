"""Pydantic schemas for purchase order endpoints.

Defines request/response models for purchase order lifecycle operations
including creation, approval, goods receipt, and cancellation.

Satisfies Requirements: 9.1, 9.3, 9.4, 9.7
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Request Schemas
# =============================================================================


class PurchaseOrderItemCreate(BaseModel):
    """Schema for a single line item when creating a purchase order."""

    spare_part_id: UUID = Field(
        ...,
        description="UUID of the spare part to order",
    )
    quantity_ordered: Decimal = Field(
        ...,
        gt=0,
        description="Quantity to order from the supplier",
        examples=[10],
    )
    unit_cost: Decimal = Field(
        ...,
        gt=0,
        description="Cost per unit for this line item",
        examples=[25.50],
    )

    @field_validator("quantity_ordered")
    @classmethod
    def validate_quantity(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v

    @field_validator("unit_cost")
    @classmethod
    def validate_unit_cost(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Unit cost must be greater than zero")
        return v


class PurchaseOrderCreate(BaseModel):
    """Request body for POST /api/v1/purchase-orders (create a PO).

    Requirement 9.1: Create a purchase order with supplier, line items.
    Requirement 9.2: Initial state is DRAFT.
    """

    supplier_id: UUID = Field(
        ...,
        description="UUID of the supplier to order from",
    )
    items: list[PurchaseOrderItemCreate] = Field(
        ...,
        min_length=1,
        description="Line items for the purchase order (at least one required)",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional notes for the purchase order",
    )


class PurchaseOrderCancel(BaseModel):
    """Request body for POST /api/v1/purchase-orders/{id}/cancel."""

    reason: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Reason for cancelling (required for non-draft POs)",
    )


class GoodsReceiveItemRequest(BaseModel):
    """Schema for a single line item in a goods receipt."""

    po_item_id: UUID = Field(
        ...,
        description="UUID of the PurchaseOrderItem being received against",
    )
    quantity_received: Decimal = Field(
        ...,
        gt=0,
        description="Quantity received for this line item",
        examples=[5],
    )
    unit_cost: Optional[Decimal] = Field(
        default=None,
        gt=0,
        description="Optional cost override (defaults to PO item's unit_cost)",
    )

    @field_validator("quantity_received")
    @classmethod
    def validate_quantity_received(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity received must be greater than zero")
        return v


class GoodsReceiveRequest(BaseModel):
    """Request body for POST /api/v1/purchase-orders/{id}/receive.

    Requirement 9.4: Goods received creates GRN recording received quantities.
    """

    location_id: UUID = Field(
        ...,
        description="UUID of the location where goods are being received",
    )
    items: list[GoodsReceiveItemRequest] = Field(
        ...,
        min_length=1,
        description="Line items being received (at least one required)",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional notes about this goods receipt",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class SparePartBrief(BaseModel):
    """Brief spare part info for PO items."""
    id: UUID
    name: str
    part_number: str
    brand: Optional[str] = None
    model_config = {"from_attributes": True}


class PurchaseOrderItemResponse(BaseModel):
    """Response schema for a purchase order line item."""

    id: UUID = Field(..., description="PO item UUID")
    purchase_order_id: UUID = Field(..., description="Parent PO UUID")
    spare_part_id: UUID = Field(..., description="Spare part UUID")
    quantity_ordered: Decimal = Field(..., description="Quantity ordered")
    quantity_received: Decimal = Field(..., description="Quantity received so far")
    unit_cost: Decimal = Field(..., description="Unit cost for this line item")
    spare_part: Optional[SparePartBrief] = Field(default=None, description="Spare part details")
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")

    model_config = {"from_attributes": True}


class SupplierBrief(BaseModel):
    """Brief supplier info for PO response."""
    id: UUID
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    model_config = {"from_attributes": True}


class PurchaseOrderResponse(BaseModel):
    """Response body for a single purchase order."""

    id: UUID = Field(..., description="Purchase order UUID")
    supplier_id: UUID = Field(..., description="Supplier UUID")
    status: str = Field(..., description="Current PO lifecycle status")
    total_amount: Decimal = Field(..., description="Total PO amount")
    notes: Optional[str] = Field(default=None, description="PO notes")
    created_by: Optional[UUID] = Field(default=None, description="User who created")
    approved_by: Optional[UUID] = Field(default=None, description="User who approved")
    approved_at: Optional[datetime] = Field(default=None, description="Approval timestamp")
    items: list[PurchaseOrderItemResponse] = Field(
        default_factory=list, description="Line items"
    )
    supplier: Optional[SupplierBrief] = Field(default=None, description="Supplier details")
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Updated timestamp")

    model_config = {"from_attributes": True}


class PurchaseOrderListResponse(BaseModel):
    """Response body for purchase order list with pagination metadata."""

    data: list[PurchaseOrderResponse] = Field(..., description="List of purchase orders")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )
