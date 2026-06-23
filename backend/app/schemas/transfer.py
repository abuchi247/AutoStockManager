"""Pydantic schemas for transfer endpoints.

Defines request/response models for inter-location stock transfer operations.

Satisfies Requirements: 4.2, 4.4, 4.5, 4.6
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Request Schemas
# =============================================================================


class TransferCreate(BaseModel):
    """Request body for POST /api/v1/transfers (create a transfer request).

    Requirement 4.2: Transfer request specifying source location, destination
    location, spare part, and quantity.
    """

    spare_part_id: UUID = Field(
        ...,
        description="UUID of the spare part to transfer",
    )
    source_location_id: UUID = Field(
        ...,
        description="UUID of the source location",
    )
    destination_location_id: UUID = Field(
        ...,
        description="UUID of the destination location",
    )
    quantity: Decimal = Field(
        ...,
        gt=0,
        description="Quantity to transfer (must be greater than 0)",
        examples=[10],
    )

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: Decimal) -> Decimal:
        """Ensure quantity is positive."""
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v


class TransferCancel(BaseModel):
    """Request body for POST /api/v1/transfers/{id}/cancel."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Reason for cancelling the transfer (required)",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class TransferResponse(BaseModel):
    """Response body for a single transfer."""

    id: UUID = Field(..., description="Transfer UUID")
    spare_part_id: UUID = Field(..., description="Spare part UUID")
    source_location_id: UUID = Field(..., description="Source location UUID")
    destination_location_id: UUID = Field(..., description="Destination location UUID")
    quantity: Decimal = Field(..., description="Transfer quantity")
    status: str = Field(..., description="Current transfer state")
    consumed_layer_details: Optional[list[dict]] = Field(
        default=None, description="FIFO cost layers consumed at source"
    )
    requested_by: UUID = Field(..., description="User who requested the transfer")
    approved_by: Optional[UUID] = Field(default=None, description="User who approved")
    received_by: Optional[UUID] = Field(default=None, description="User who received")
    approved_at: Optional[datetime] = Field(default=None, description="Approval timestamp")
    received_at: Optional[datetime] = Field(default=None, description="Receipt timestamp")
    cancellation_reason: Optional[str] = Field(
        default=None, description="Reason for cancellation"
    )
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Updated timestamp")
    created_by: Optional[str] = Field(default=None, description="Created by user")
    updated_by: Optional[str] = Field(default=None, description="Updated by user")

    model_config = {"from_attributes": True}


class TransferListResponse(BaseModel):
    """Response body for transfer list with pagination metadata."""

    data: list[TransferResponse] = Field(..., description="List of transfers")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )
