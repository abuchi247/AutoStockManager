"""
Invoice model for storing generated PDF invoices.

This module defines the Invoice model which stores generated invoice PDFs
linked to sale transactions. Each invoice record contains the PDF binary data,
invoice number, and format (A4 or THERMAL).

Satisfies Requirements:
- 14.1: PDF invoices with company logo, details, line items, totals
- 14.2: Support A4 full-page and thermal receipt (80mm width) formats
- 14.5: Store generated PDF for future retrieval
"""

import enum
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, LargeBinary, String, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class InvoiceFormat(str, enum.Enum):
    """Supported invoice output formats."""

    A4 = "A4"
    THERMAL = "THERMAL"


class Invoice(BaseModel):
    """Invoice model storing generated PDF data.

    Represents a generated invoice PDF linked to a sale transaction.
    Invoices can be generated in A4 (full-page) or THERMAL (80mm receipt)
    formats and stored for future retrieval.

    Satisfies Requirements:
    - 14.1: PDF invoices with company logo, details, line items, totals
    - 14.2: Support A4 full-page and thermal receipt (80mm width) formats
    - 14.5: Store generated PDF for future retrieval

    Columns:
        sale_id        - FK to the sale this invoice was generated from
        invoice_number - Invoice number (matches sale invoice_number)
        pdf_data       - Binary PDF content stored for retrieval
        format         - Invoice format (A4 or THERMAL)

    Relationships:
        sale - The sale transaction this invoice belongs to
    """

    __tablename__ = "invoices"

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sales.id"),
        nullable=False,
        comment="Sale transaction this invoice was generated from",
    )

    # -------------------------------------------------------------------------
    # Invoice Identification
    # -------------------------------------------------------------------------
    invoice_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Invoice number (matches sale invoice_number)",
    )

    # -------------------------------------------------------------------------
    # PDF Storage
    # -------------------------------------------------------------------------
    pdf_data: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="Binary PDF content of the generated invoice",
    )

    # -------------------------------------------------------------------------
    # Format
    # -------------------------------------------------------------------------
    format: Mapped[InvoiceFormat] = mapped_column(
        Enum(InvoiceFormat, name="invoice_format", create_constraint=True),
        nullable=False,
        default=InvoiceFormat.A4,
        comment="Invoice format: A4 (full-page) or THERMAL (80mm receipt)",
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    sale: Mapped["Sale"] = relationship(  # noqa: F821
        "Sale",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice(id={self.id}, invoice_number='{self.invoice_number}', "
            f"format={self.format})>"
        )
