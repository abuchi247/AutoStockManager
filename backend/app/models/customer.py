"""
Customer model for the Auto Spare Parts ERP system.

This module defines the Customer model which stores customer profiles
including contact information, credit limits, and account status.

Satisfies Requirements:
- 6.1: Store customer profiles with name, phone, email, address, tax_id,
       credit_limit, and account_status
- 6.2: Maintain complete purchase history for each customer
"""

import enum
from decimal import Decimal
from typing import Optional

from sqlalchemy import Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, SoftDeleteMixin


class AccountStatus(str, enum.Enum):
    """Enumeration of customer account statuses."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Customer(BaseModel, SoftDeleteMixin):
    """Customer model for storing customer profiles.

    Represents a customer entity in the ERP system with contact information,
    credit management fields, and account status tracking.

    Satisfies Requirement 6.1: THE Customer_Manager SHALL store customer
    profiles with: name, phone number, email, address, tax identification
    number, credit limit, and account status.

    Columns:
        name           - Customer full name (required)
        phone          - Phone number (nullable)
        email          - Email address (nullable)
        address        - Full address (nullable, text field)
        tax_id         - Tax identification number (nullable)
        credit_limit   - Maximum credit allowed (default 0)
        account_status - Current status: active, suspended, or closed
    """

    __tablename__ = "customers"

    # -------------------------------------------------------------------------
    # Customer Information
    # -------------------------------------------------------------------------
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Customer full name",
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Customer phone number",
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Customer email address",
    )

    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Customer full address",
    )

    tax_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Tax identification number",
    )

    # -------------------------------------------------------------------------
    # Credit Management
    # -------------------------------------------------------------------------
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Maximum credit limit allowed for this customer",
    )

    account_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AccountStatus.ACTIVE.value,
        comment="Account status: active, suspended, or closed",
    )

    def __repr__(self) -> str:
        return (
            f"<Customer(id={self.id}, name='{self.name}', "
            f"account_status='{self.account_status}', "
            f"credit_limit={self.credit_limit})>"
        )
