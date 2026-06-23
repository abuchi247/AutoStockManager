"""
Customer Credit Ledger model.

This module defines the immutable append-only ledger that tracks every credit
transaction for a customer: sales (debits), payments (credits), adjustments,
and returns. The sum of all amounts for a given customer_id equals their
current outstanding balance.

The ledger is append-only — entries are never modified or deleted. This ensures
a complete audit trail and enables point-in-time balance reconstruction.

Satisfies Requirement 6.4: THE Customer_Manager SHALL calculate the current
customer balance as the sum of all debit and credit entries in the
Customer_Credit_Ledger for that customer.

Satisfies Requirement 7.1: THE Credit_Ledger SHALL record entries for the
following transaction types: sale, payment, adjustment, and return.

Satisfies Requirement 7.7: THE Credit_Ledger SHALL enforce credit limit
validation at the database transaction layer whenever a debit entry is written.

Satisfies Requirement 7.9: THE Credit_Ledger SHALL validate credit limits at
transaction confirmation time rather than at draft creation time.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CreditTransactionType(str, enum.Enum):
    """Classification of credit ledger transaction types.

    Satisfies Requirement 7.1: THE Credit_Ledger SHALL record entries for
    the following transaction types: sale, payment, adjustment, and return.
    """

    SALE = "SALE"
    PAYMENT = "PAYMENT"
    ADJUSTMENT = "ADJUSTMENT"
    RETURN = "RETURN"


class CustomerCreditLedger(Base):
    """Immutable ledger entry recording a single customer credit transaction.

    This model intentionally does NOT inherit from BaseModel (which has
    updated_at/updated_by) because ledger entries are append-only and should
    never be modified after creation. It uses its own id, created_at, and
    created_by fields.

    Amount convention:
        - Positive amounts represent debits (charges to the customer, e.g., sales)
        - Negative amounts represent credits (reductions, e.g., payments, returns)
        - The sum of all amounts for a customer = outstanding balance

    Columns:
        id               - UUID primary key
        customer_id      - FK to customers table
        transaction_type - Type of transaction (SALE, PAYMENT, ADJUSTMENT, RETURN)
        amount           - Signed decimal (positive=debit, negative=credit)
        reference_type   - Type of the originating document (sale, payment, adjustment, return)
        reference_id     - UUID of the originating document
        notes            - Optional text notes (required for adjustments per Req 7.5)
        created_by       - UUID of the user who created this entry
        created_at       - Timestamp when this entry was created (immutable)

    Indexes:
        - Index on (customer_id, created_at) for balance queries and aging analysis
    """

    __tablename__ = "customer_credit_ledger"

    __table_args__ = (
        Index(
            "ix_credit_ledger_customer_created",
            "customer_id",
            "created_at",
        ),
    )

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique identifier for this credit ledger entry",
    )

    # -------------------------------------------------------------------------
    # Core Transaction Data
    # -------------------------------------------------------------------------
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="The customer this entry belongs to (FK to customers)",
    )

    transaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of transaction (SALE, PAYMENT, ADJUSTMENT, RETURN)",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
        comment="Signed amount: positive=debit (charge), negative=credit (payment/return)",
    )

    reference_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of the originating document (sale, payment, adjustment, return)",
    )

    reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="UUID of the originating document",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional notes (required for adjustments per Req 7.5)",
    )

    # -------------------------------------------------------------------------
    # Audit Fields (append-only — no updated_at/updated_by)
    # -------------------------------------------------------------------------
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="UUID of the user who created this entry",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp when this ledger entry was created (immutable)",
    )

    def __repr__(self) -> str:
        return (
            f"<CustomerCreditLedger(id={self.id}, customer_id={self.customer_id}, "
            f"type={self.transaction_type}, amount={self.amount})>"
        )
