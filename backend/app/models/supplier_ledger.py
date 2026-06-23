"""
Supplier Ledger model.

This module defines the immutable append-only ledger that tracks every
financial transaction for a supplier: purchases (debits representing amounts
owed to supplier), payments (credits reducing amounts owed), and adjustments.
The sum of all amounts for a given supplier_id equals their current
outstanding balance (accounts payable).

The ledger is append-only — entries are never modified or deleted. This ensures
a complete audit trail and enables point-in-time balance reconstruction.

Satisfies Requirement 1.4: THE ERP_System SHALL maintain accounts payable
balances derived from supplier purchase and payment records.

Satisfies Requirement 8.3: THE Supplier_Manager SHALL calculate the current
supplier balance as the sum of all purchase and payment entries for that supplier.

Satisfies Requirement 8.5: WHEN a supplier payment is recorded, THE
Supplier_Manager SHALL reduce the outstanding balance for that supplier
by the payment amount.
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


class SupplierTransactionType(str, enum.Enum):
    """Classification of supplier ledger transaction types.

    Satisfies Requirement 8.3: Track purchase and payment entries.
    """

    PURCHASE = "PURCHASE"
    PAYMENT = "PAYMENT"
    ADJUSTMENT = "ADJUSTMENT"
    RETURN = "RETURN"


class SupplierLedger(Base):
    """Immutable ledger entry recording a single supplier financial transaction.

    This model intentionally does NOT inherit from BaseModel (which has
    updated_at/updated_by) because ledger entries are append-only and should
    never be modified after creation. It uses its own id, created_at, and
    created_by fields.

    Amount convention:
        - Positive amounts represent debits (amounts owed to supplier, e.g., purchases)
        - Negative amounts represent credits (reductions, e.g., payments, returns)
        - The sum of all amounts for a supplier = outstanding balance (accounts payable)

    Columns:
        id               - UUID primary key
        supplier_id      - FK to suppliers table
        transaction_type - Type of transaction (PURCHASE, PAYMENT, ADJUSTMENT, RETURN)
        amount           - Signed decimal (positive=debit/owed, negative=credit/paid)
        reference_type   - Type of the originating document (purchase_order, payment, etc.)
        reference_id     - UUID of the originating document
        notes            - Optional text notes
        created_by       - UUID of the user who created this entry
        created_at       - Timestamp when this entry was created (immutable)

    Indexes:
        - Index on (supplier_id, created_at) for balance queries and aging analysis
    """

    __tablename__ = "supplier_ledger"

    __table_args__ = (
        Index(
            "ix_supplier_ledger_supplier_created",
            "supplier_id",
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
        comment="Unique identifier for this supplier ledger entry",
    )

    # -------------------------------------------------------------------------
    # Core Transaction Data
    # -------------------------------------------------------------------------
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="The supplier this entry belongs to (FK to suppliers)",
    )

    transaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of transaction (PURCHASE, PAYMENT, ADJUSTMENT, RETURN)",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
        comment="Signed amount: positive=debit (owed), negative=credit (paid)",
    )

    reference_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of the originating document (purchase_order, payment, adjustment)",
    )

    reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="UUID of the originating document",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional notes for this ledger entry",
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
            f"<SupplierLedger(id={self.id}, supplier_id={self.supplier_id}, "
            f"type={self.transaction_type}, amount={self.amount})>"
        )
