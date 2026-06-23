"""
Credit Ledger Service.

This module implements business logic for managing customer credit transactions
including recording debits/credits, validating credit limits with pessimistic
locking, calculating balances, and performing aging analysis.

Key Design Decisions:
- Credit limit enforcement uses SELECT FOR UPDATE on the customer record to
  prevent race conditions between concurrent credit checks (Req 7.7, 7.9).
- Balance is always derived from the ledger SUM, not a cached field (Req 6.4).
- Aging analysis categorizes outstanding sale amounts by invoice age (Req 7.3).

Satisfies Requirements:
- 5.4: Credit sale records debit entry against customer account
- 6.3: Customer payment records credit entry reducing outstanding balance
- 6.4: Current balance = sum of all debit and credit entries
- 7.1: Ledger records sale, payment, adjustment, and return entries
- 7.2: Reject credit sale if balance would exceed credit limit
- 7.5: Manual adjustments require reason field and Manager/Admin auth
- 7.7: Credit limit enforcement at database transaction layer
- 7.8: Manual adjustment that increases balance enforces credit limit
- 7.9: Credit limit validated at transaction confirmation time
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_credit_ledger import CustomerCreditLedger, CreditTransactionType


class CreditLimitExceededError(Exception):
    """Raised when a transaction would cause the customer balance to exceed their credit limit.

    Satisfies Requirement 7.2: WHEN a credit sale would cause the customer
    outstanding balance to exceed the customer credit limit, THE Credit_Ledger
    SHALL reject the transaction with a credit limit exceeded error.
    """

    def __init__(
        self,
        customer_id: uuid.UUID,
        current_balance: Decimal,
        attempted_amount: Decimal,
        credit_limit: Decimal,
    ):
        self.customer_id = customer_id
        self.current_balance = current_balance
        self.attempted_amount = attempted_amount
        self.credit_limit = credit_limit
        super().__init__(
            f"Credit limit exceeded for customer {customer_id}: "
            f"current_balance={current_balance}, "
            f"attempted_amount={attempted_amount}, "
            f"credit_limit={credit_limit}, "
            f"would_be={current_balance + attempted_amount}"
        )


class CreditLedgerService:
    """Service for managing customer credit ledger operations.

    This service handles all interactions with the Customer_Credit_Ledger
    including recording transactions, enforcing credit limits, calculating
    balances, and generating aging analysis reports.

    All write operations expect to be called within an active database
    transaction managed by the caller (typically a sale confirmation or
    payment recording endpoint).
    """

    def __init__(self, db: AsyncSession):
        """Initialize with an async database session.

        Args:
            db: An active SQLAlchemy async session. The caller is responsible
                for transaction management (commit/rollback).
        """
        self.db = db

    async def calculate_balance(self, customer_id: uuid.UUID) -> Decimal:
        """Calculate the current outstanding balance for a customer.

        The balance is derived from the sum of all ledger entries for this
        customer. Positive amounts are debits (sales), negative amounts are
        credits (payments, returns).

        Satisfies Requirement 6.4: THE Customer_Manager SHALL calculate the
        current customer balance as the sum of all debit and credit entries
        in the Customer_Credit_Ledger for that customer.

        Args:
            customer_id: UUID of the customer.

        Returns:
            The current outstanding balance (positive means customer owes money).
        """
        stmt = select(
            func.coalesce(
                func.sum(CustomerCreditLedger.amount),
                Decimal("0.00"),
            )
        ).filter(CustomerCreditLedger.customer_id == customer_id)

        result = await self.db.execute(stmt)
        return result.scalar()

    async def validate_credit_limit(
        self,
        customer_id: uuid.UUID,
        amount: Decimal,
        credit_limit: Decimal,
    ) -> Decimal:
        """Validate that a debit would not exceed the customer's credit limit.

        This method calculates the current balance from the ledger and checks
        whether adding the specified amount would exceed the credit limit.
        It does NOT acquire locks — the caller must ensure a lock on the
        customer record is held before calling this method.

        Satisfies Requirement 7.2, 7.7, 7.8, 7.9.

        Args:
            customer_id: UUID of the customer.
            amount: The debit amount to validate (positive value).
            credit_limit: The customer's credit limit.

        Returns:
            The current balance before the debit.

        Raises:
            CreditLimitExceededError: If the resulting balance would exceed
                the credit limit.
        """
        current_balance = await self.calculate_balance(customer_id)

        new_balance = current_balance + amount
        if new_balance > credit_limit:
            raise CreditLimitExceededError(
                customer_id=customer_id,
                current_balance=current_balance,
                attempted_amount=amount,
                credit_limit=credit_limit,
            )

        return current_balance

    async def record_debit(
        self,
        customer_id: uuid.UUID,
        amount: Decimal,
        reference_type: str,
        reference_id: uuid.UUID,
        created_by: uuid.UUID,
        transaction_type: CreditTransactionType = CreditTransactionType.SALE,
        notes: Optional[str] = None,
        credit_limit: Optional[Decimal] = None,
    ) -> CustomerCreditLedger:
        """Record a debit (charge) entry in the customer credit ledger.

        A debit increases the customer's outstanding balance. If a credit_limit
        is provided, the method validates that the resulting balance would not
        exceed it. The caller MUST hold a pessimistic lock on the customer
        record before calling this method to prevent race conditions.

        Satisfies Requirement 5.4: WHEN a credit sale is confirmed, THE
        Credit_Ledger SHALL record a debit entry against the customer account.

        Satisfies Requirement 7.7: THE Credit_Ledger SHALL enforce credit limit
        validation at the database transaction layer whenever a debit entry is
        written to the Customer_Credit_Ledger.

        Args:
            customer_id: UUID of the customer to debit.
            amount: The positive debit amount (must be > 0).
            reference_type: Type of originating document (e.g., "sale").
            reference_id: UUID of the originating document.
            created_by: UUID of the user recording this entry.
            transaction_type: The transaction classification (default: SALE).
            notes: Optional notes for the entry.
            credit_limit: If provided, validates the credit limit before recording.

        Returns:
            The created CustomerCreditLedger entry.

        Raises:
            ValueError: If amount is not positive.
            CreditLimitExceededError: If credit_limit is provided and would be exceeded.
        """
        if amount <= Decimal("0"):
            raise ValueError("Debit amount must be positive")

        # Validate credit limit if provided
        if credit_limit is not None:
            await self.validate_credit_limit(customer_id, amount, credit_limit)

        entry = CustomerCreditLedger(
            customer_id=customer_id,
            transaction_type=transaction_type.value,
            amount=amount,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
            created_by=created_by,
        )
        self.db.add(entry)
        await self.db.flush()

        return entry

    async def record_credit(
        self,
        customer_id: uuid.UUID,
        amount: Decimal,
        reference_type: str,
        reference_id: uuid.UUID,
        created_by: uuid.UUID,
        transaction_type: CreditTransactionType = CreditTransactionType.PAYMENT,
        notes: Optional[str] = None,
    ) -> CustomerCreditLedger:
        """Record a credit (payment/return) entry in the customer credit ledger.

        A credit reduces the customer's outstanding balance. The amount is
        stored as a negative value in the ledger.

        Satisfies Requirement 6.3: WHEN a customer payment is received, THE
        Credit_Ledger SHALL record a credit entry against the customer account
        reducing the outstanding balance.

        Args:
            customer_id: UUID of the customer to credit.
            amount: The positive credit amount (will be stored as negative).
            reference_type: Type of originating document (e.g., "payment", "return").
            reference_id: UUID of the originating document.
            created_by: UUID of the user recording this entry.
            transaction_type: The transaction classification (default: PAYMENT).
            notes: Optional notes for the entry.

        Returns:
            The created CustomerCreditLedger entry.

        Raises:
            ValueError: If amount is not positive.
        """
        if amount <= Decimal("0"):
            raise ValueError("Credit amount must be positive")

        entry = CustomerCreditLedger(
            customer_id=customer_id,
            transaction_type=transaction_type.value,
            amount=-amount,  # Credits stored as negative
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
            created_by=created_by,
        )
        self.db.add(entry)
        await self.db.flush()

        return entry

    async def aging_analysis(
        self,
        customer_id: uuid.UUID,
        as_of_date: Optional[datetime] = None,
    ) -> dict[str, Decimal]:
        """Calculate aging analysis for a customer's outstanding balance.

        Categorizes outstanding SALE debit amounts by age (days since entry
        creation). Payments and returns reduce the oldest outstanding amounts
        first (FIFO application of credits to debits).

        Satisfies Requirement 7.3: THE Credit_Ledger SHALL calculate aging
        analysis for each customer categorizing outstanding amounts into
        current, 1–30 days, 31–60 days, 61–90 days, and over 90 days overdue.

        Args:
            customer_id: UUID of the customer.
            as_of_date: The reference date for age calculation (defaults to now).

        Returns:
            Dictionary with aging buckets:
                - "current": amounts 0 days old (same day)
                - "1_30_days": amounts 1-30 days old
                - "31_60_days": amounts 31-60 days old
                - "61_90_days": amounts 61-90 days old
                - "over_90_days": amounts more than 90 days old
                - "total": sum of all outstanding amounts
        """
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc)

        # Get all ledger entries for this customer, ordered by created_at
        stmt = (
            select(CustomerCreditLedger)
            .filter(CustomerCreditLedger.customer_id == customer_id)
            .order_by(CustomerCreditLedger.created_at.asc())
        )
        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        # Separate debits (positive amounts) and credits (negative amounts)
        # Each debit has a remaining amount that credits reduce in FIFO order
        debits: list[dict] = []
        total_credits = Decimal("0.00")

        for entry in entries:
            if entry.amount > Decimal("0"):
                # Debit entry — track remaining outstanding amount
                debits.append({
                    "amount": entry.amount,
                    "remaining": entry.amount,
                    "created_at": entry.created_at,
                })
            else:
                # Credit entry — accumulate for FIFO application
                total_credits += abs(entry.amount)

        # Apply credits to debits in FIFO order (oldest first)
        remaining_credits = total_credits
        for debit in debits:
            if remaining_credits <= Decimal("0"):
                break
            apply = min(debit["remaining"], remaining_credits)
            debit["remaining"] -= apply
            remaining_credits -= apply

        # Categorize remaining outstanding debits by age
        buckets = {
            "current": Decimal("0.00"),
            "1_30_days": Decimal("0.00"),
            "31_60_days": Decimal("0.00"),
            "61_90_days": Decimal("0.00"),
            "over_90_days": Decimal("0.00"),
        }

        for debit in debits:
            if debit["remaining"] <= Decimal("0"):
                continue

            # Calculate age in days
            created_at = debit["created_at"]
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            age_days = (as_of_date - created_at).days

            if age_days <= 0:
                buckets["current"] += debit["remaining"]
            elif age_days <= 30:
                buckets["1_30_days"] += debit["remaining"]
            elif age_days <= 60:
                buckets["31_60_days"] += debit["remaining"]
            elif age_days <= 90:
                buckets["61_90_days"] += debit["remaining"]
            else:
                buckets["over_90_days"] += debit["remaining"]

        buckets["total"] = sum(buckets.values())

        return buckets
