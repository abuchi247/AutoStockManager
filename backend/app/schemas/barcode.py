"""Pydantic schemas for barcode API endpoints.

Defines request and response models for barcode generation, lookup,
and management operations.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Response Schemas
# =============================================================================


class BarcodeInfoResponse(BaseModel):
    """Response schema for barcode information."""

    spare_part_id: UUID = Field(description="UUID of the spare part")
    barcode: str = Field(description="The barcode value")
    barcode_type: str = Field(description="Type of barcode: 'system' or 'manufacturer'")
    part_number: str = Field(description="The spare part's part number")
    part_name: str = Field(description="The spare part's name")

    model_config = {"from_attributes": True}


class BarcodeGenerateResponse(BaseModel):
    """Response schema for barcode generation."""

    spare_part_id: UUID = Field(description="UUID of the spare part")
    barcode: str = Field(description="The generated barcode value")
    barcode_type: str = Field(description="Type: 'system'")
    message: str = Field(description="Status message")


class BarcodeLookupResponse(BaseModel):
    """Response schema for barcode lookup."""

    spare_part_id: UUID = Field(description="UUID of the matched spare part")
    part_number: str = Field(description="Part number")
    barcode: str = Field(description="Barcode value")
    name: str = Field(description="Spare part name")
    brand: Optional[str] = Field(default=None, description="Brand name")
    selling_price: float = Field(description="Selling price")
    unit_of_measure: str = Field(description="Unit of measure")
    barcode_type: str = Field(description="Type of barcode: 'system' or 'manufacturer'")

    model_config = {"from_attributes": True}


class BarcodeDecodeResponse(BaseModel):
    """Response schema for barcode decoding."""

    value: str = Field(description="The raw barcode value")
    type: str = Field(description="Type of barcode: 'system' or 'manufacturer'")
    part_number_hint: Optional[str] = Field(
        default=None, description="Extracted part number hint (for system barcodes)"
    )


# =============================================================================
# Request Schemas
# =============================================================================


class BarcodeAssignRequest(BaseModel):
    """Request schema for assigning a manufacturer barcode."""

    barcode: str = Field(
        min_length=1,
        max_length=255,
        description="The manufacturer-provided barcode value",
    )


class BarcodeLookupRequest(BaseModel):
    """Request schema for barcode lookup."""

    barcode: str = Field(
        min_length=1,
        max_length=255,
        description="The barcode value to look up",
    )
