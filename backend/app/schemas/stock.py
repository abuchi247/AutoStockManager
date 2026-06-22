"""Pydantic schemas for stock query endpoints.

Defines response models for stock status cache queries.

Satisfies Requirements: 18.1, 18.3, 18.8
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Response Schemas
# =============================================================================


class StockItemResponse(BaseModel):
    """Response body for a single stock cache entry."""

    id: UUID = Field(..., description="Stock cache entry unique identifier")
    spare_part_id: UUID = Field(..., description="Spare part identifier")
    location_id: UUID = Field(..., description="Location identifier")
    current_quantity: float = Field(..., description="Current stock quantity at this location")
    last_reconciled_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last reconciliation against movement ledger",
    )
    created_at: Optional[datetime] = Field(default=None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    # Nested spare part info for convenience
    spare_part_name: Optional[str] = Field(
        default=None,
        description="Spare part display name (from relationship)",
    )
    spare_part_number: Optional[str] = Field(
        default=None,
        description="Spare part number (from relationship)",
    )

    model_config = {"from_attributes": True}


class StockLocationResponse(BaseModel):
    """Response body for stock at a specific location."""

    location_id: UUID = Field(..., description="Location identifier")
    location_name: Optional[str] = Field(default=None, description="Location display name")
    data: list[StockItemResponse] = Field(
        default_factory=list,
        description="List of stock items at this location",
    )
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )
