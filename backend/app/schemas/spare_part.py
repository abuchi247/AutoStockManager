"""Pydantic schemas for spare parts inventory endpoints.

Defines request/response models for spare part CRUD operations and search.

Satisfies Requirements: 3.1, 3.2, 3.4, 3.5
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Request Schemas
# =============================================================================


class SparePartCreate(BaseModel):
    """Request body for POST /api/v1/spare-parts (create a new spare part)."""

    part_number: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique part identification number",
        examples=["SP-001"],
    )
    barcode: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Scannable barcode value (unique when present)",
        examples=["8901234567890"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Product display name",
        examples=["Brake Pad Set - Front"],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Detailed product description",
    )
    brand: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Manufacturer or brand name",
        examples=["Bosch"],
    )
    category_id: Optional[UUID] = Field(
        default=None,
        description="Primary category UUID",
    )
    subcategory_id: Optional[UUID] = Field(
        default=None,
        description="Subcategory UUID (optional)",
    )
    vehicle_compatibility: Optional[list[str]] = Field(
        default=None,
        description="List of compatible vehicles",
        examples=[["Toyota Camry 2018-2023", "Honda Accord 2020-2023"]],
    )
    unit_of_measure: str = Field(
        default="PCS",
        max_length=50,
        description="Unit of measure (e.g., PCS, BOX, LTR, KG)",
        examples=["PCS"],
    )
    cost_price: Decimal = Field(
        ...,
        ge=0,
        description="Purchase/cost price",
        examples=[25.50],
    )
    selling_price: Decimal = Field(
        ...,
        ge=0,
        description="Retail selling price",
        examples=[45.00],
    )
    min_stock_level: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Minimum stock threshold for reorder alerts",
        examples=[10],
    )
    max_stock_level: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Maximum stock capacity",
        examples=[100],
    )
    reorder_quantity: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Default quantity to reorder when stock is low",
        examples=[50],
    )


class SparePartUpdate(BaseModel):
    """Request body for PUT /api/v1/spare-parts/{id} (partial update)."""

    part_number: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Unique part identification number",
    )
    barcode: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Scannable barcode value",
    )
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Product display name",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Detailed product description",
    )
    brand: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Manufacturer or brand name",
    )
    category_id: Optional[UUID] = Field(
        default=None,
        description="Primary category UUID",
    )
    subcategory_id: Optional[UUID] = Field(
        default=None,
        description="Subcategory UUID",
    )
    vehicle_compatibility: Optional[list[str]] = Field(
        default=None,
        description="List of compatible vehicles",
    )
    unit_of_measure: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Unit of measure",
    )
    cost_price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Purchase/cost price",
    )
    selling_price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Retail selling price",
    )
    min_stock_level: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Minimum stock threshold",
    )
    max_stock_level: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Maximum stock capacity",
    )
    reorder_quantity: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Default quantity to reorder",
    )


class SparePartSearch(BaseModel):
    """Query parameters for spare part search.

    Satisfies Requirement 3.5: Search by part_number, barcode, name, brand,
    category, and vehicle_compatibility.
    """

    q: Optional[str] = Field(
        default=None,
        description="General search term (searches part_number, barcode, name, brand)",
    )
    part_number: Optional[str] = Field(
        default=None,
        description="Filter by exact or partial part number",
    )
    barcode: Optional[str] = Field(
        default=None,
        description="Filter by exact barcode",
    )
    name: Optional[str] = Field(
        default=None,
        description="Filter by partial name match",
    )
    brand: Optional[str] = Field(
        default=None,
        description="Filter by brand name",
    )
    category_id: Optional[UUID] = Field(
        default=None,
        description="Filter by category UUID",
    )
    vehicle_compatibility: Optional[str] = Field(
        default=None,
        description="Filter by vehicle compatibility (partial match in JSON array)",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class CategoryResponse(BaseModel):
    """Embedded category information in spare part responses."""

    id: UUID = Field(..., description="Category UUID")
    name: str = Field(..., description="Category display name")
    parent_id: Optional[UUID] = Field(default=None, description="Parent category UUID")

    model_config = {"from_attributes": True}


class SparePartResponse(BaseModel):
    """Response body for a single spare part."""

    id: UUID = Field(..., description="Spare part UUID")
    part_number: str = Field(..., description="Unique part identification number")
    barcode: Optional[str] = Field(default=None, description="Scannable barcode value")
    name: str = Field(..., description="Product display name")
    description: Optional[str] = Field(default=None, description="Detailed description")
    brand: Optional[str] = Field(default=None, description="Manufacturer or brand")
    category_id: Optional[UUID] = Field(default=None, description="Primary category UUID")
    subcategory_id: Optional[UUID] = Field(default=None, description="Subcategory UUID")
    vehicle_compatibility: Optional[list[str]] = Field(
        default=None, description="Compatible vehicles"
    )
    unit_of_measure: str = Field(..., description="Unit of measure")
    cost_price: Decimal = Field(..., description="Purchase/cost price")
    selling_price: Decimal = Field(..., description="Retail selling price")
    min_stock_level: Decimal = Field(..., description="Minimum stock threshold")
    max_stock_level: Decimal = Field(..., description="Maximum stock capacity")
    reorder_quantity: Decimal = Field(..., description="Default reorder quantity")
    category: Optional[CategoryResponse] = Field(
        default=None, description="Category details"
    )
    subcategory: Optional[CategoryResponse] = Field(
        default=None, description="Subcategory details"
    )
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last updated timestamp")
    created_by: Optional[str] = Field(default=None, description="Created by user")
    updated_by: Optional[str] = Field(default=None, description="Updated by user")

    model_config = {"from_attributes": True}


class SparePartListResponse(BaseModel):
    """Response body for spare part list with pagination metadata."""

    data: list[SparePartResponse] = Field(..., description="List of spare parts")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )
