"""Pydantic schemas for customer management endpoints.

Defines request/response models for customer CRUD operations and purchase history.

Satisfies Requirements: 6.1, 6.2
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.customer import AccountStatus


# =============================================================================
# Request Schemas
# =============================================================================


class CustomerCreate(BaseModel):
    """Request body for POST /api/v1/customers (create a new customer)."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Customer full name",
        examples=["Ade Motors Ltd"],
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Customer phone number",
        examples=["+234 801 234 5678"],
    )
    email: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Customer email address",
        examples=["info@ademotors.com"],
    )
    address: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Customer full address",
        examples=["123 Main Street, Lagos, Nigeria"],
    )
    tax_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Tax identification number",
        examples=["TIN-12345678"],
    )
    credit_limit: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Maximum credit limit for this customer",
        examples=[50000.00],
    )
    account_status: Optional[str] = Field(
        default=AccountStatus.ACTIVE.value,
        description="Account status: active, suspended, or closed",
        examples=["active"],
    )

    @field_validator("account_status")
    @classmethod
    def validate_account_status(cls, v: Optional[str]) -> str:
        if v is None:
            return AccountStatus.ACTIVE.value
        valid_statuses = [s.value for s in AccountStatus]
        if v not in valid_statuses:
            raise ValueError(
                f"Invalid account status '{v}'. Must be one of: {valid_statuses}"
            )
        return v


class CustomerUpdate(BaseModel):
    """Request body for PUT /api/v1/customers/{id} (partial update)."""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Customer full name",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Customer phone number",
    )
    email: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Customer email address",
    )
    address: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Customer full address",
    )
    tax_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Tax identification number",
    )
    credit_limit: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Maximum credit limit",
    )
    account_status: Optional[str] = Field(
        default=None,
        description="Account status: active, suspended, or closed",
    )

    @field_validator("account_status")
    @classmethod
    def validate_account_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_statuses = [s.value for s in AccountStatus]
        if v not in valid_statuses:
            raise ValueError(
                f"Invalid account status '{v}'. Must be one of: {valid_statuses}"
            )
        return v


# =============================================================================
# Response Schemas
# =============================================================================


class CustomerResponse(BaseModel):
    """Response body for a single customer."""

    id: UUID = Field(..., description="Customer UUID")
    name: str = Field(..., description="Customer full name")
    phone: Optional[str] = Field(default=None, description="Phone number")
    email: Optional[str] = Field(default=None, description="Email address")
    address: Optional[str] = Field(default=None, description="Full address")
    tax_id: Optional[str] = Field(default=None, description="Tax ID")
    credit_limit: Decimal = Field(..., description="Credit limit")
    account_status: str = Field(..., description="Account status")
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Updated timestamp")
    created_by: Optional[str] = Field(default=None, description="Created by user")
    updated_by: Optional[str] = Field(default=None, description="Updated by user")

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    """Response body for customer list with pagination metadata."""

    data: list[CustomerResponse] = Field(..., description="List of customers")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )


class PurchaseHistoryItem(BaseModel):
    """A single purchase history entry for a customer."""

    sale_id: UUID = Field(..., description="Sale UUID")
    invoice_number: Optional[str] = Field(default=None, description="Invoice number")
    status: str = Field(..., description="Sale status")
    payment_type: str = Field(..., description="Payment type")
    total_amount: Decimal = Field(..., description="Total sale amount")
    created_at: Optional[datetime] = Field(default=None, description="Sale date")

    model_config = {"from_attributes": True}


class PurchaseHistoryResponse(BaseModel):
    """Response body for customer purchase history."""

    data: list[PurchaseHistoryItem] = Field(..., description="Purchase history items")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )
