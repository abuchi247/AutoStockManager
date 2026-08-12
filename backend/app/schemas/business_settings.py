"""Pydantic schemas for business settings endpoints."""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Sub-models for JSONB array elements
# ---------------------------------------------------------------------------

class PhoneEntry(BaseModel):
    """A single phone number entry."""

    label: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description='Short label, e.g. "Main", "WhatsApp", "Abuja Branch"',
        examples=["Main"],
    )
    number: str = Field(
        ...,
        min_length=5,
        max_length=30,
        description="Phone number in any local or international format",
        examples=["08012345678"],
    )

    model_config = {"str_strip_whitespace": True}


class BankAccountEntry(BaseModel):
    """A single bank account entry."""

    bank_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description='Bank name, e.g. "First Bank", "GTBank"',
        examples=["First Bank"],
    )
    account_number: str = Field(
        ...,
        min_length=5,
        max_length=30,
        description="NUBAN or account number",
        examples=["0123456789"],
    )
    account_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name on the account as it appears on statements",
        examples=["Chidi Auto Parts Ltd"],
    )

    model_config = {"str_strip_whitespace": True}


# Annotated types used in the list fields
PhoneList = Annotated[
    list[PhoneEntry],
    Field(max_length=10, description="Up to 10 phone numbers"),
]
BankAccountList = Annotated[
    list[BankAccountEntry],
    Field(max_length=10, description="Up to 10 bank accounts"),
]


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

class BusinessSettingsUpdate(BaseModel):
    """Request body for PUT /api/v1/business-settings.

    All fields are optional — only the keys present in the request body are
    applied (PATCH semantics via model_dump(exclude_unset=True)).
    """

    business_name: Optional[str] = Field(
        default=None, max_length=255, description="Legal business name"
    )
    address: Optional[str] = Field(
        default=None, max_length=2000, description="Business address"
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
        default=None, max_length=1000, description="Invoice footer text"
    )

    # New multi-value fields
    phones: Optional[list[PhoneEntry]] = Field(
        default=None,
        max_length=10,
        description="List of phone numbers (max 10)",
    )
    bank_accounts: Optional[list[BankAccountEntry]] = Field(
        default=None,
        max_length=10,
        description="List of bank accounts (max 10)",
    )

    @field_validator("phones", mode="before")
    @classmethod
    def validate_phones(cls, v: object) -> object:
        if isinstance(v, list) and len(v) > 10:
            raise ValueError("A maximum of 10 phone numbers is allowed")
        return v

    @field_validator("bank_accounts", mode="before")
    @classmethod
    def validate_bank_accounts(cls, v: object) -> object:
        if isinstance(v, list) and len(v) > 10:
            raise ValueError("A maximum of 10 bank accounts is allowed")
        return v


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class BusinessSettingsResponse(BaseModel):
    """Response body for GET and PUT /api/v1/business-settings."""

    id: UUID = Field(..., description="Settings record ID")
    business_name: str = Field(..., description="Legal business name")
    address: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    tax_id: Optional[str] = Field(default=None)
    website: Optional[str] = Field(default=None)
    logo_base64: Optional[str] = Field(default=None)
    invoice_footer: Optional[str] = Field(default=None)

    # Multi-value fields — always returned as lists (never null)
    phones: list[PhoneEntry] = Field(default_factory=list)
    bank_accounts: list[BankAccountEntry] = Field(default_factory=list)

    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)

    model_config = {"from_attributes": True}
