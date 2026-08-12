"""
Business Settings model.

Stores company/business information used on invoices, receipts, and reports.
This is a single-row table — only one business profile exists per installation.

Phone numbers and bank accounts are stored as JSONB arrays so an operator can
maintain several contacts and payment channels without schema changes:

  phones:        [{"label": "Main", "number": "08012345678"}, ...]
  bank_accounts: [{"bank_name": "First Bank",
                   "account_number": "0123456789",
                   "account_name": "Chidi Auto Parts Ltd"}, ...]

The legacy scalar columns (phone, bank_name, bank_account_number,
bank_account_name) are retained so existing deployments are not broken.
Migration 0009 moves any data in those columns into the JSONB arrays and
the application exclusively reads/writes the arrays going forward.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BusinessSettings(Base):
    """Single-row table storing business profile information."""

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

    # ── Multi-value contacts (JSONB arrays) ──────────────────────────────────
    # Each element: {"label": str, "number": str}
    phones: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment='Phone numbers: [{"label": "Main", "number": "08012345678"}]',
    )

    # Each element: {"bank_name": str, "account_number": str, "account_name": str}
    bank_accounts: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment='Bank accounts: [{"bank_name": "...", "account_number": "...", "account_name": "..."}]',
    )

    # ── Scalar fields ────────────────────────────────────────────────────────
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

    # ── Legacy scalar columns — kept for backward-compatibility ──────────────
    # Migration 0009 copies any values here into the JSONB arrays above.
    # These columns are no longer written by the application but are preserved
    # so a downgrade does not lose data.
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="[DEPRECATED] Single phone — superseded by phones JSONB array",
    )

    bank_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="[DEPRECATED] Bank name — superseded by bank_accounts JSONB array",
    )

    bank_account_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="[DEPRECATED] Account number — superseded by bank_accounts JSONB array",
    )

    bank_account_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="[DEPRECATED] Account holder — superseded by bank_accounts JSONB array",
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
