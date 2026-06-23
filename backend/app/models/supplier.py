"""
Supplier model for the Auto Spare Parts ERP system.

This module defines the Supplier model which stores supplier profiles
including contact information, payment terms, and account status.

Satisfies Requirements:
- 8.1: Store supplier profiles with name, contact_person, phone, email,
       address, tax_id, payment_terms, and account_status
- 8.2: Maintain complete purchase history for each supplier
"""

import enum
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, SoftDeleteMixin


class SupplierAccountStatus(str, enum.Enum):
    """Enumeration of supplier account statuses."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Supplier(BaseModel, SoftDeleteMixin):
    """Supplier model for storing supplier profiles.

    Represents a supplier entity in the ERP system with contact information,
    payment terms, and account status tracking.

    Satisfies Requirement 8.1: THE Supplier_Manager SHALL store supplier
    profiles with: name, contact person, phone number, email, address,
    tax identification number, payment terms, and account status.

    Columns:
        name            - Supplier name (required)
        contact_person  - Contact person name (nullable)
        phone           - Phone number (nullable)
        email           - Email address (nullable)
        address         - Full address (nullable, text field)
        tax_id          - Tax identification number (nullable)
        payment_terms   - Payment terms e.g. "Net 30" (nullable)
        account_status  - Current status: active, suspended, or closed
    """

    __tablename__ = "suppliers"

    # -------------------------------------------------------------------------
    # Supplier Information
    # -------------------------------------------------------------------------
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Supplier name",
    )

    contact_person: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Contact person name",
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Supplier phone number",
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Supplier email address",
    )

    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Supplier full address",
    )

    tax_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Tax identification number",
    )

    payment_terms: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Payment terms e.g. Net 30, Net 60",
    )

    # -------------------------------------------------------------------------
    # Account Status
    # -------------------------------------------------------------------------
    account_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SupplierAccountStatus.ACTIVE.value,
        comment="Account status: active, suspended, or closed",
    )

    def __repr__(self) -> str:
        return (
            f"<Supplier(id={self.id}, name='{self.name}', "
            f"account_status='{self.account_status}')>"
        )
