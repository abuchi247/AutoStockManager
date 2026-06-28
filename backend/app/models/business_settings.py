"""
Business Settings model.

Stores company/business information used on invoices, receipts, and reports.
This is a single-row table — only one business profile exists per installation.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BusinessSettings(Base):
    """Single-row table storing business profile information.

    Used to populate invoice headers, report footers, and other
    documents that require business identification.
    """

    __tablename__ = "business_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    business_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="My Business",
        comment="Legal business name displayed on invoices",
    )

    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Business address",
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Business phone number",
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Business email address",
    )

    tax_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Tax identification number (TIN/VAT)",
    )

    website: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Business website URL",
    )

    logo_base64: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Base64-encoded logo image for invoices",
    )

    invoice_footer: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default="Thank you for your patronage",
        comment="Custom footer text for invoices",
    )

    bank_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Bank name for payment instructions",
    )

    bank_account_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Bank account number",
    )

    bank_account_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Account holder name",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<BusinessSettings(name='{self.business_name}')>"
