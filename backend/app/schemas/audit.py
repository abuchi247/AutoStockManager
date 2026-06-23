"""Pydantic schemas for audit session endpoints.

Defines request/response models for inventory audit operations including
session creation, physical count submission, approval, reconciliation,
and recount flagging.

Satisfies Requirements: 11.1, 11.2, 11.3, 11.4
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Request Schemas
# =============================================================================


class AuditSessionCreate(BaseModel):
    """Request body for POST /api/v1/audits (initiate an audit session).

    Requirement 11.1: Support two audit types: CYCLE_COUNT and FULL_STOCK_COUNT.
    Requirement 11.2: Create session recording audit_type, location, date, and assigned users.
    """

    location_id: UUID = Field(
        ...,
        description="UUID of the location being audited",
    )
    audit_type: str = Field(
        ...,
        description="Type of audit: CYCLE_COUNT or FULL_STOCK_COUNT",
        examples=["CYCLE_COUNT", "FULL_STOCK_COUNT"],
    )
    spare_part_ids: Optional[list[UUID]] = Field(
        default=None,
        description="List of spare part IDs for CYCLE_COUNT (ignored for FULL_STOCK_COUNT)",
    )

    @field_validator("audit_type")
    @classmethod
    def validate_audit_type(cls, v: str) -> str:
        """Ensure audit_type is valid."""
        valid_types = {"CYCLE_COUNT", "FULL_STOCK_COUNT"}
        if v not in valid_types:
            raise ValueError(f"audit_type must be one of: {', '.join(valid_types)}")
        return v


class AuditCountSubmit(BaseModel):
    """Request body for POST /api/v1/audits/{id}/counts (submit a physical count).

    Requirement 11.3: Calculate variance as counted_quantity - system_quantity (snapshot).
    """

    spare_part_id: UUID = Field(
        ...,
        description="UUID of the spare part being counted",
    )
    counted_quantity: Decimal = Field(
        ...,
        ge=0,
        description="The physical count quantity (must be >= 0)",
        examples=[42],
    )

    @field_validator("counted_quantity")
    @classmethod
    def validate_counted_quantity(cls, v: Decimal) -> Decimal:
        """Ensure counted quantity is non-negative."""
        if v < 0:
            raise ValueError("Counted quantity must be non-negative")
        return v


# =============================================================================
# Response Schemas
# =============================================================================


class AuditSnapshotItemResponse(BaseModel):
    """Response model for a single audit snapshot item."""

    id: UUID = Field(..., description="Snapshot item UUID")
    session_id: UUID = Field(..., description="Parent audit session UUID")
    spare_part_id: UUID = Field(..., description="Spare part UUID")
    snapshot_quantity: Decimal = Field(..., description="Frozen stock quantity at audit initiation")
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")

    model_config = {"from_attributes": True}


class AuditCountResponse(BaseModel):
    """Response model for a single audit count entry."""

    id: UUID = Field(..., description="Audit count UUID")
    session_id: UUID = Field(..., description="Parent audit session UUID")
    spare_part_id: UUID = Field(..., description="Spare part UUID")
    counted_quantity: Decimal = Field(..., description="Physical count quantity")
    variance: Decimal = Field(..., description="Variance: counted - snapshot")
    counted_by: UUID = Field(..., description="User who performed the count")
    counted_at: datetime = Field(..., description="Timestamp of the count")
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")

    model_config = {"from_attributes": True}


class AuditSessionResponse(BaseModel):
    """Response body for a single audit session."""

    id: UUID = Field(..., description="Audit session UUID")
    location_id: UUID = Field(..., description="Location being audited")
    audit_type: str = Field(..., description="Type of audit (CYCLE_COUNT or FULL_STOCK_COUNT)")
    status: str = Field(..., description="Current session status")
    snapshot_timestamp: datetime = Field(..., description="Timestamp when stock was frozen")
    initiated_by: UUID = Field(..., description="User who initiated the audit")
    approved_by: Optional[UUID] = Field(default=None, description="User who approved")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    snapshot_items: Optional[list[AuditSnapshotItemResponse]] = Field(
        default=None, description="Frozen stock quantities"
    )
    counts: Optional[list[AuditCountResponse]] = Field(
        default=None, description="Submitted physical counts"
    )
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Updated timestamp")

    model_config = {"from_attributes": True}


class AuditSessionListResponse(BaseModel):
    """Response body for audit session list with pagination metadata."""

    data: list[AuditSessionResponse] = Field(..., description="List of audit sessions")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )


class ReconciliationMovementResponse(BaseModel):
    """Response model for a post-snapshot movement in the reconciliation view."""

    ledger_entry_id: UUID = Field(..., description="Ledger entry UUID")
    spare_part_id: UUID = Field(..., description="Spare part UUID")
    quantity_change: Decimal = Field(..., description="Quantity change (positive or negative)")
    movement_type: str = Field(..., description="Type of movement")
    reference_type: str = Field(..., description="Reference type (e.g., sale, transfer)")
    reference_id: UUID = Field(..., description="Reference entity UUID")
    created_at: datetime = Field(..., description="Movement timestamp")
    created_by: UUID = Field(..., description="User who created the movement")


class ReconciliationResponse(BaseModel):
    """Response body for reconciliation view showing post-snapshot movements."""

    session_id: UUID = Field(..., description="Audit session UUID")
    movements: list[ReconciliationMovementResponse] = Field(
        ..., description="Post-snapshot movements"
    )


class RecountFlagResponse(BaseModel):
    """Response model for a spare part flagged as requiring re-count."""

    spare_part_id: UUID = Field(..., description="Spare part UUID")
    movement_count: int = Field(..., description="Number of movements since snapshot")
    net_quantity_change: Decimal = Field(..., description="Net quantity change since snapshot")


class RecountFlagsResponse(BaseModel):
    """Response body for recount flags endpoint."""

    session_id: UUID = Field(..., description="Audit session UUID")
    flags: list[RecountFlagResponse] = Field(
        ..., description="Parts requiring re-count"
    )
