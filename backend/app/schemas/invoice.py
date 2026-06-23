"""Pydantic schemas for invoice endpoints.

Defines request and response models for invoice generation and retrieval.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InvoiceGenerateRequest(BaseModel):
    """Request schema for generating an invoice."""

    sale_id: uuid.UUID = Field(..., description="UUID of the sale to generate invoice for")
    format: str = Field(
        default="A4",
        description="Invoice format: A4 (full-page) or THERMAL (80mm receipt)",
    )
    overwrite: bool = Field(
        default=False,
        description="If True, overwrite existing invoice for this sale/format",
    )


class InvoiceResponse(BaseModel):
    """Response schema for invoice metadata (excludes PDF binary data)."""

    id: uuid.UUID
    sale_id: uuid.UUID
    invoice_number: str
    format: str
    created_at: datetime

    model_config = {"from_attributes": True}
