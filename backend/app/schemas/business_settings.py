"""Pydantic schemas for business settings endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BusinessSettingsUpdate(BaseModel):
    """Request body for updating business settings."""

    business_name: Optional[str] = Field(
        default=None, max_length=255, description="Legal business name"
    )
    address: Optional[str] = Field(
        default=None, max_length=2000, description="Business address"
    )
    phone: Optional[str] = Field(
        default=None, max_length=50, description="Business phone number"
    )
    email: Optional[str] = Field(
        default=None, max_length=255, description="Business email"
    )
    tax_id: Optional[str] = Field(
        default=None, max_length=100, description="Tax ID (TIN/VAT)"
    )
    website: Optional[str] = Field(
        default=None, max_length=255, description="Business website"
    )
    logo_base64: Optional[str] = Field(
        default=None, description="Base64-encoded logo image"
    )
    invoice_footer: Optional[str] = Field(
        default=None, max_length=500, description="Invoice footer text"
    )
    bank_name: Optional[str] = Field(
        default=None, max_length=255, description="Bank name"
    )
    bank_account_number: Optional[str] = Field(
        default=None, max_length=100, description="Bank account number"
    )
    bank_account_name: Optional[str] = Field(
        default=None, max_length=255, description="Account holder name"
    )


class BusinessSettingsResponse(BaseModel):
    """Response body for business settings."""

    id: UUID = Field(..., description="Settings record ID")
    business_name: str = Field(..., description="Legal business name")
    address: Optional[str] = Field(default=None, description="Business address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    email: Optional[str] = Field(default=None, description="Email address")
    tax_id: Optional[str] = Field(default=None, description="Tax ID")
    website: Optional[str] = Field(default=None, description="Website URL")
    logo_base64: Optional[str] = Field(default=None, description="Logo (base64)")
    invoice_footer: Optional[str] = Field(default=None, description="Invoice footer")
    bank_name: Optional[str] = Field(default=None, description="Bank name")
    bank_account_number: Optional[str] = Field(default=None, description="Account number")
    bank_account_name: Optional[str] = Field(default=None, description="Account holder")
    updated_at: Optional[datetime] = Field(default=None, description="Last updated")
    updated_by: Optional[str] = Field(default=None, description="Updated by user")

    model_config = {"from_attributes": True}
