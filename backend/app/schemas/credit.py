"""Pydantic schemas for credit management endpoints.

Defines request/response models for payment recording, manual adjustments,
credit ledger queries, and aging analysis.

Satisfies Requirements: 6.3, 7.1, 7.3, 7.5
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Request Schemas
# =============================================================================


class PaymentCreate(BaseModel):
    """Request body for POST /api/v1/credit/payments.

    Records a customer payment that reduces their outstanding balance.
    Satisfies Requirement 6.3.
    """

    customer_id: UUID = Field(
        ...,
        description="UUID of the customer making the payment",
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Payment amount (must be positive)",
        examples=[5000.00],
    )
    sale_id: Optional[UUID] = Field(
        default=None,
        description="Optional UUID of the sale this payment is for (links payment to specific transaction)",
    )
    reference_id: Optional[UUID] = Field(
        default=None,
        description="Optional UUID of the payment reference document",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional notes about the payment",
        examples=["Cash payment received at counter"],
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("Payment amount must be positive")
        return v


class AdjustmentCreate(BaseModel):
    """Request body for POST /api/v1/credit/adjustments.

    Records a manual credit adjustment. Requires notes/reason field.
    Only Manager/Admin can perform adjustments.

    Satisfies Requirement 7.5: Manual adjustments require reason field
    and Manager or Admin authorization.
    """

    customer_id: UUID = Field(
        ...,
        description="UUID of the customer to adjust",
    )
    amount: Decimal = Field(
        ...,
        description="Adjustment amount. Positive = increase balance (debit), negative = decrease balance (credit).",
        examples=[1500.00, -500.00],
    )
    reference_id: Optional[UUID] = Field(
        default=None,
        description="Optional UUID of the adjustment reference document",
    )
    notes: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Required reason/notes for the adjustment",
        examples=["Correcting invoice error from 2024-01-15"],
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v == Decimal("0"):
            raise ValueError("Adjustment amount cannot be zero")
        return v


# =============================================================================
# Response Schemas
# =============================================================================


class CreditLedgerEntryResponse(BaseModel):
    """Response model for a single credit ledger entry."""

    id: UUID = Field(..., description="Ledger entry UUID")
    customer_id: UUID = Field(..., description="Customer UUID")
    transaction_type: str = Field(..., description="Transaction type (SALE, PAYMENT, ADJUSTMENT, RETURN)")
    amount: Decimal = Field(..., description="Signed amount (positive=debit, negative=credit)")
    reference_type: str = Field(..., description="Type of originating document")
    reference_id: UUID = Field(..., description="UUID of originating document")
    notes: Optional[str] = Field(default=None, description="Entry notes")
    created_by: UUID = Field(..., description="User who created this entry")
    created_at: Optional[datetime] = Field(default=None, description="Entry timestamp")

    model_config = {"from_attributes": True}


class CreditLedgerListResponse(BaseModel):
    """Response body for customer credit ledger with pagination."""

    data: list[CreditLedgerEntryResponse] = Field(..., description="Ledger entries")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )


class AgingAnalysisResponse(BaseModel):
    """Response model for customer aging analysis.

    Satisfies Requirement 7.3: Categorize outstanding amounts into
    current, 1-30 days, 31-60 days, 61-90 days, and over 90 days.
    """

    customer_id: UUID = Field(..., description="Customer UUID")
    current: Decimal = Field(..., description="Amounts 0 days old (same day)")
    days_1_30: Decimal = Field(..., description="Amounts 1-30 days old")
    days_31_60: Decimal = Field(..., description="Amounts 31-60 days old")
    days_61_90: Decimal = Field(..., description="Amounts 61-90 days old")
    over_90_days: Decimal = Field(..., description="Amounts more than 90 days old")
    total: Decimal = Field(..., description="Total outstanding balance")


class PaymentResponse(BaseModel):
    """Response body for a successful payment recording."""

    entry: CreditLedgerEntryResponse = Field(..., description="The created ledger entry")
    new_balance: Decimal = Field(..., description="Updated customer balance after payment")


class AdjustmentResponse(BaseModel):
    """Response body for a successful adjustment recording."""

    entry: CreditLedgerEntryResponse = Field(..., description="The created ledger entry")
    new_balance: Decimal = Field(..., description="Updated customer balance after adjustment")
