"""Pydantic schemas for location management endpoints.

Defines request/response models for location CRUD operations.

Satisfies Requirement 4.1: Location management for warehouses and retail branches.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================


class LocationCreate(BaseModel):
    """Request body for POST /api/v1/locations (create a new location)."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name of the location",
        examples=["Main Warehouse"],
    )
    type: str = Field(
        default="warehouse",
        max_length=50,
        description="Location type (e.g., 'warehouse', 'retail_branch')",
        examples=["warehouse"],
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Physical address of the location",
        examples=["123 Industrial Ave, Lagos"],
    )
    is_active: bool = Field(
        default=True,
        description="Whether this location is currently operational",
    )


class LocationUpdate(BaseModel):
    """Request body for PUT /api/v1/locations/{id} (partial update)."""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Human-readable name of the location",
    )
    type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Location type (e.g., 'warehouse', 'retail_branch')",
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Physical address of the location",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether this location is currently operational",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class LocationResponse(BaseModel):
    """Response body for a single location."""

    id: UUID = Field(..., description="Location UUID")
    name: str = Field(..., description="Location name")
    type: str = Field(..., description="Location type")
    address: Optional[str] = Field(default=None, description="Physical address")
    is_active: bool = Field(..., description="Whether location is operational")
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Updated timestamp")
    created_by: Optional[str] = Field(default=None, description="Created by user")
    updated_by: Optional[str] = Field(default=None, description="Updated by user")

    model_config = {"from_attributes": True}


class LocationListResponse(BaseModel):
    """Response body for location list with pagination metadata."""

    data: list[LocationResponse] = Field(..., description="List of locations")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )
