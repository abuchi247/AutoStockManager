"""Supplier service implementing CRUD operations, balance calculation, and aging analysis.

Provides create, read, update, soft-delete, balance calculation, aging
analysis, purchase history, and payment recording for supplier records.

Satisfies Requirements:
- 8.1: Store supplier profiles with all required attributes
- 8.2: Maintain complete purchase history for each supplier
- 8.3: Calculate current supplier balance from purchase and payment entries
- 8.4: Calculate supplier aging analysis
- 8.5: Record supplier payments reducing outstanding balance
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.models.supplier import Supplier
from app.models.supplier_ledger import SupplierLedger, SupplierTransactionType
from app.schemas.supplier import SupplierCreate, SupplierUpdate


# =============================================================================
# Custom Exceptions
# =============================================================================


class SupplierNotFoundError(Exception):
    """Raised when a supplier with the given ID is not found."""

    def __init__(self, supplier_id: UUID):
        self.message = f"Supplier with ID '{supplier_id}' not found"
        super().__init__(self.message)


class DuplicateSupplierError(Exception):
    """Raised when a duplicate supplier is detected."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


# =============================================================================
# Supplier Service
# =============================================================================


class SupplierService:
    """Service handling supplier CRUD operations, balance, and aging analysis.

    All methods operate on non-deleted (active) records only, respecting
    the soft-delete pattern used throughout the ERP system.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the supplier service.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    async def create_supplier(
        self, data: SupplierCreate, created_by: Optional[str] = None
    ) -> Supplier:
        """Create a new supplier record.

        Satisfies Requirement 8.1: Store supplier profiles with name,
        contact_person, phone, email, address, tax_id, payment_terms,
        and account_status.

        Args:
            data: Validated supplier creation data.
            created_by: User identifier performing the creation.

        Returns:
            The newly created Supplier instance.
        """
        supplier = Supplier(
            name=data.name,
            contact_person=data.contact_person,
            phone=data.phone,
            email=data.email,
            address=data.address,
            tax_id=data.tax_id,
            payment_terms=data.payment_terms,
            account_status=data.account_status,
            created_by=created_by,
        )
        self.db.add(supplier)
        await self.db.flush()
        await self.db.refresh(supplier)
        return supplier

    # -------------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------------

    async def get_supplier(self, supplier_id: UUID) -> Supplier:
        """Retrieve a single supplier by ID.

        Args:
            supplier_id: UUID of the supplier to retrieve.

        Returns:
            The Supplier instance.

        Raises:
            SupplierNotFoundError: If no active supplier with that ID exists.
        """
        stmt = select(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        supplier = result.scalar_one_or_none()

        if supplier is None:
            raise SupplierNotFoundError(supplier_id)

        return supplier

    async def list_suppliers(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
    ) -> tuple[list[Supplier], int]:
        """List suppliers with pagination and optional search.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            search: Optional search term to filter by name, contact_person, phone, or email.

        Returns:
            Tuple of (list of suppliers, total count).
        """
        filters = [Supplier.deleted_at.is_(None)]

        if search:
            search_term = f"%{search}%"
            from sqlalchemy import or_

            filters.append(
                or_(
                    Supplier.name.ilike(search_term),
                    Supplier.contact_person.ilike(search_term),
                    Supplier.phone.ilike(search_term),
                    Supplier.email.ilike(search_term),
                )
            )

        # Count total
        count_stmt = select(func.count(Supplier.id)).filter(*filters)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(Supplier)
            .filter(*filters)
            .order_by(Supplier.name.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        suppliers = list(result.scalars().all())

        return suppliers, total

    # -------------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------------

    async def update_supplier(
        self,
        supplier_id: UUID,
        data: SupplierUpdate,
        updated_by: Optional[str] = None,
    ) -> Supplier:
        """Update an existing supplier's attributes.

        Only non-None fields in the update data are applied.

        Args:
            supplier_id: UUID of the supplier to update.
            data: Validated partial update data.
            updated_by: User identifier performing the update.

        Returns:
            The updated Supplier instance.

        Raises:
            SupplierNotFoundError: If no active supplier with that ID exists.
        """
        supplier = await self.get_supplier(supplier_id)

        # Apply updates for non-None fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(supplier, field, value)

        if updated_by:
            supplier.updated_by = updated_by

        await self.db.flush()
        await self.db.refresh(supplier)
        return supplier

    # -------------------------------------------------------------------------
    # Soft Delete
    # -------------------------------------------------------------------------

    async def delete_supplier(
        self, supplier_id: UUID, deleted_by: Optional[str] = None
    ) -> Supplier:
        """Soft-delete a supplier.

        Marks the record with deleted_at and deleted_by timestamps instead
        of physically removing it.

        Args:
            supplier_id: UUID of the supplier to delete.
            deleted_by: User identifier performing the deletion.

        Returns:
            The soft-deleted Supplier instance.

        Raises:
            SupplierNotFoundError: If no active supplier with that ID exists.
        """
        supplier = await self.get_supplier(supplier_id)
        supplier.soft_delete(deleted_by=deleted_by)
        await self.db.flush()
        return supplier

    # -------------------------------------------------------------------------
    # Purchase History
    # -------------------------------------------------------------------------

    async def get_purchase_history(
        self,
        supplier_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PurchaseOrder], int]:
        """Retrieve purchase history for a supplier.

        Satisfies Requirement 8.2: Maintain complete purchase history for
        each supplier including all purchase orders, goods receipts, dates,
        and amounts.

        Args:
            supplier_id: UUID of the supplier.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (list of purchase orders, total count).

        Raises:
            SupplierNotFoundError: If no active supplier with that ID exists.
        """
        # Verify supplier exists
        await self.get_supplier(supplier_id)

        # Count total purchase orders for this supplier
        count_stmt = select(func.count(PurchaseOrder.id)).filter(
            PurchaseOrder.supplier_id == supplier_id,
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(PurchaseOrder)
            .filter(PurchaseOrder.supplier_id == supplier_id)
            .order_by(PurchaseOrder.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        orders = list(result.scalars().all())

        return orders, total

    # -------------------------------------------------------------------------
    # Balance Calculation
    # -------------------------------------------------------------------------

    async def calculate_balance(self, supplier_id: UUID) -> Decimal:
        """Calculate the current outstanding balance for a supplier.

        Satisfies Requirement 8.3: THE Supplier_Manager SHALL calculate the
        current supplier balance as the sum of all purchase and payment entries
        for that supplier.

        The balance is derived from the sum of all SupplierLedger entries.
        Positive amounts are debits (purchases owed), negative amounts are
        credits (payments made).

        Args:
            supplier_id: UUID of the supplier.

        Returns:
            The current outstanding balance (positive = amount owed to supplier).

        Raises:
            SupplierNotFoundError: If no active supplier with that ID exists.
        """
        # Verify supplier exists
        await self.get_supplier(supplier_id)

        stmt = select(
            func.coalesce(
                func.sum(SupplierLedger.amount),
                Decimal("0.00"),
            )
        ).filter(SupplierLedger.supplier_id == supplier_id)

        result = await self.db.execute(stmt)
        return result.scalar()

    # -------------------------------------------------------------------------
    # Record Purchase Debit
    # -------------------------------------------------------------------------

    async def record_purchase_debit(
        self,
        supplier_id: UUID,
        amount: Decimal,
        reference_id: UUID,
        created_by: UUID,
        notes: Optional[str] = None,
    ) -> SupplierLedger:
        """Record a purchase debit entry in the supplier ledger.

        When goods are received from a supplier, the amount owed increases.
        This creates a positive (debit) entry in the supplier ledger.

        Args:
            supplier_id: UUID of the supplier.
            amount: The positive debit amount (must be > 0).
            reference_id: UUID of the originating purchase order or GRN.
            created_by: UUID of the user recording this entry.
            notes: Optional notes for the entry.

        Returns:
            The created SupplierLedger entry.

        Raises:
            ValueError: If amount is not positive.
            SupplierNotFoundError: If supplier does not exist.
        """
        if amount <= Decimal("0"):
            raise ValueError("Purchase debit amount must be positive")

        # Verify supplier exists
        await self.get_supplier(supplier_id)

        entry = SupplierLedger(
            supplier_id=supplier_id,
            transaction_type=SupplierTransactionType.PURCHASE.value,
            amount=amount,
            reference_type="purchase_order",
            reference_id=reference_id,
            notes=notes,
            created_by=created_by,
        )
        self.db.add(entry)
        await self.db.flush()

        return entry

    # -------------------------------------------------------------------------
    # Record Payment
    # -------------------------------------------------------------------------

    async def record_payment(
        self,
        supplier_id: UUID,
        amount: Decimal,
        reference_id: UUID,
        created_by: UUID,
        notes: Optional[str] = None,
    ) -> SupplierLedger:
        """Record a payment credit entry in the supplier ledger.

        Satisfies Requirement 8.5: WHEN a supplier payment is recorded,
        THE Supplier_Manager SHALL reduce the outstanding balance for that
        supplier by the payment amount.

        A payment reduces the outstanding balance. The amount is stored as
        a negative value in the ledger.

        Args:
            supplier_id: UUID of the supplier.
            amount: The positive payment amount (will be stored as negative).
            reference_id: UUID of the payment reference document.
            created_by: UUID of the user recording this entry.
            notes: Optional notes for the entry.

        Returns:
            The created SupplierLedger entry.

        Raises:
            ValueError: If amount is not positive.
            SupplierNotFoundError: If supplier does not exist.
        """
        if amount <= Decimal("0"):
            raise ValueError("Payment amount must be positive")

        # Verify supplier exists
        await self.get_supplier(supplier_id)

        entry = SupplierLedger(
            supplier_id=supplier_id,
            transaction_type=SupplierTransactionType.PAYMENT.value,
            amount=-amount,  # Credits stored as negative
            reference_type="payment",
            reference_id=reference_id,
            notes=notes,
            created_by=created_by,
        )
        self.db.add(entry)
        await self.db.flush()

        return entry

    # -------------------------------------------------------------------------
    # Aging Analysis
    # -------------------------------------------------------------------------

    async def calculate_aging(
        self,
        supplier_id: UUID,
        as_of_date: Optional[datetime] = None,
    ) -> dict:
        """Calculate aging analysis for a supplier's outstanding balance.

        Satisfies Requirement 8.4: THE Supplier_Manager SHALL calculate
        supplier aging analysis categorizing outstanding amounts into
        current, 1-30 days, 31-60 days, 61-90 days, and over 90 days overdue.

        Uses FIFO allocation of credits against debits (oldest debits are
        reduced first by payments).

        Args:
            supplier_id: UUID of the supplier.
            as_of_date: The reference date for age calculation (defaults to now).

        Returns:
            Dictionary with aging buckets:
            - current: amounts 0 days old (same day)
            - days_1_30: amounts 1-30 days overdue
            - days_31_60: amounts 31-60 days overdue
            - days_61_90: amounts 61-90 days overdue
            - days_over_90: amounts over 90 days overdue
            - total: total outstanding balance

        Raises:
            SupplierNotFoundError: If no active supplier with that ID exists.
        """
        # Verify supplier exists
        await self.get_supplier(supplier_id)

        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc)

        # Get all ledger entries for this supplier, ordered by created_at
        stmt = (
            select(SupplierLedger)
            .filter(SupplierLedger.supplier_id == supplier_id)
            .order_by(SupplierLedger.created_at.asc())
        )
        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        # Separate debits (positive amounts) and credits (negative amounts)
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
            "days_1_30": Decimal("0.00"),
            "days_31_60": Decimal("0.00"),
            "days_61_90": Decimal("0.00"),
            "days_over_90": Decimal("0.00"),
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
                buckets["days_1_30"] += debit["remaining"]
            elif age_days <= 60:
                buckets["days_31_60"] += debit["remaining"]
            elif age_days <= 90:
                buckets["days_61_90"] += debit["remaining"]
            else:
                buckets["days_over_90"] += debit["remaining"]

        buckets["total"] = sum(buckets.values())

        return buckets
