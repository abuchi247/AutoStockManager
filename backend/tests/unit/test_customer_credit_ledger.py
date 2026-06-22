"""Unit tests for CustomerCreditLedger model and CreditLedgerService."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.customer_credit_ledger import (
    CustomerCreditLedger,
    CreditTransactionType,
)
from app.services.credit_ledger_service import (
    CreditLedgerService,
    CreditLimitExceededError,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestCustomerCreditLedgerModel:
    """Tests for the CustomerCreditLedger SQLAlchemy model."""

    def test_tablename(self):
        """Model should use 'customer_credit_ledger' as the table name."""
        assert CustomerCreditLedger.__tablename__ == "customer_credit_ledger"

    def test_id_column(self):
        """Model should have a UUID primary key."""
        col = CustomerCreditLedger.__table__.columns["id"]
        assert col.primary_key is True

    def test_customer_id_column(self):
        """Model should have a non-nullable customer_id column."""
        col = CustomerCreditLedger.__table__.columns["customer_id"]
        assert col.nullable is False

    def test_transaction_type_column(self):
        """Model should have a non-nullable transaction_type column."""
        col = CustomerCreditLedger.__table__.columns["transaction_type"]
        assert col.nullable is False

    def test_amount_column(self):
        """Model should have a non-nullable amount column."""
        col = CustomerCreditLedger.__table__.columns["amount"]
        assert col.nullable is False

    def test_reference_type_column(self):
        """Model should have a non-nullable reference_type column."""
        col = CustomerCreditLedger.__table__.columns["reference_type"]
        assert col.nullable is False

    def test_reference_id_column(self):
        """Model should have a non-nullable reference_id column."""
        col = CustomerCreditLedger.__table__.columns["reference_id"]
        assert col.nullable is False

    def test_notes_column_nullable(self):
        """Model should have a nullable notes column."""
        col = CustomerCreditLedger.__table__.columns["notes"]
        assert col.nullable is True

    def test_created_by_column(self):
        """Model should have a non-nullable created_by column."""
        col = CustomerCreditLedger.__table__.columns["created_by"]
        assert col.nullable is False

    def test_created_at_column(self):
        """Model should have a non-nullable created_at column."""
        col = CustomerCreditLedger.__table__.columns["created_at"]
        assert col.nullable is False

    def test_no_updated_at_column(self):
        """Model should NOT have an updated_at column (append-only)."""
        columns = CustomerCreditLedger.__table__.columns.keys()
        assert "updated_at" not in columns

    def test_no_updated_by_column(self):
        """Model should NOT have an updated_by column (append-only)."""
        columns = CustomerCreditLedger.__table__.columns.keys()
        assert "updated_by" not in columns

    def test_instance_creation(self):
        """Can create a CustomerCreditLedger instance with expected fields."""
        customer_id = uuid.uuid4()
        reference_id = uuid.uuid4()
        created_by = uuid.uuid4()

        entry = CustomerCreditLedger(
            customer_id=customer_id,
            transaction_type=CreditTransactionType.SALE.value,
            amount=Decimal("500.00"),
            reference_type="sale",
            reference_id=reference_id,
            notes=None,
            created_by=created_by,
        )

        assert entry.customer_id == customer_id
        assert entry.transaction_type == CreditTransactionType.SALE.value
        assert entry.amount == Decimal("500.00")
        assert entry.reference_type == "sale"
        assert entry.reference_id == reference_id
        assert entry.notes is None
        assert entry.created_by == created_by

    def test_instance_with_notes(self):
        """Can create an entry with notes (required for adjustments per Req 7.5)."""
        entry = CustomerCreditLedger(
            customer_id=uuid.uuid4(),
            transaction_type=CreditTransactionType.ADJUSTMENT.value,
            amount=Decimal("100.00"),
            reference_type="adjustment",
            reference_id=uuid.uuid4(),
            notes="Manager approved write-off for damaged goods",
            created_by=uuid.uuid4(),
        )

        assert entry.notes == "Manager approved write-off for damaged goods"

    def test_composite_index_exists(self):
        """Model should have a composite index on (customer_id, created_at)."""
        indexes = CustomerCreditLedger.__table__.indexes
        index_names = {idx.name for idx in indexes}
        assert "ix_credit_ledger_customer_created" in index_names

    def test_repr(self):
        """Model __repr__ should include key fields."""
        customer_id = uuid.uuid4()
        entry = CustomerCreditLedger(
            id=uuid.uuid4(),
            customer_id=customer_id,
            transaction_type=CreditTransactionType.PAYMENT.value,
            amount=Decimal("-200.00"),
            reference_type="payment",
            reference_id=uuid.uuid4(),
            created_by=uuid.uuid4(),
        )
        repr_str = repr(entry)
        assert "CustomerCreditLedger" in repr_str
        assert str(customer_id) in repr_str


class TestCreditTransactionType:
    """Tests for the CreditTransactionType enum."""

    def test_sale_type(self):
        assert CreditTransactionType.SALE.value == "SALE"

    def test_payment_type(self):
        assert CreditTransactionType.PAYMENT.value == "PAYMENT"

    def test_adjustment_type(self):
        assert CreditTransactionType.ADJUSTMENT.value == "ADJUSTMENT"

    def test_return_type(self):
        assert CreditTransactionType.RETURN.value == "RETURN"

    def test_all_types_defined(self):
        """Should have exactly four transaction types per Req 7.1."""
        assert len(CreditTransactionType) == 4


# =============================================================================
# CreditLimitExceededError Tests
# =============================================================================


class TestCreditLimitExceededError:
    """Tests for the CreditLimitExceededError exception."""

    def test_error_attributes(self):
        """Error should store all relevant details."""
        customer_id = uuid.uuid4()
        error = CreditLimitExceededError(
            customer_id=customer_id,
            current_balance=Decimal("800.00"),
            attempted_amount=Decimal("300.00"),
            credit_limit=Decimal("1000.00"),
        )

        assert error.customer_id == customer_id
        assert error.current_balance == Decimal("800.00")
        assert error.attempted_amount == Decimal("300.00")
        assert error.credit_limit == Decimal("1000.00")

    def test_error_message(self):
        """Error message should describe the limit violation."""
        error = CreditLimitExceededError(
            customer_id=uuid.uuid4(),
            current_balance=Decimal("800.00"),
            attempted_amount=Decimal("300.00"),
            credit_limit=Decimal("1000.00"),
        )

        assert "Credit limit exceeded" in str(error)
        assert "800.00" in str(error)
        assert "300.00" in str(error)
        assert "1000.00" in str(error)


# =============================================================================
# CreditLedgerService Tests
# =============================================================================


class TestCreditLedgerServiceCalculateBalance:
    """Tests for CreditLedgerService.calculate_balance."""

    @pytest.mark.asyncio
    async def test_calculate_balance_returns_sum(self):
        """calculate_balance should return the sum of all ledger entries."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = Decimal("1500.00")
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)
        balance = await service.calculate_balance(uuid.uuid4())

        assert balance == Decimal("1500.00")
        db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_balance_zero_for_no_entries(self):
        """calculate_balance should return 0 when no entries exist (coalesce)."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = Decimal("0.00")
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)
        balance = await service.calculate_balance(uuid.uuid4())

        assert balance == Decimal("0.00")


class TestCreditLedgerServiceValidateCreditLimit:
    """Tests for CreditLedgerService.validate_credit_limit."""

    @pytest.mark.asyncio
    async def test_within_limit_passes(self):
        """Should return current balance when within limit."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = Decimal("500.00")
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)
        balance = await service.validate_credit_limit(
            customer_id=uuid.uuid4(),
            amount=Decimal("400.00"),
            credit_limit=Decimal("1000.00"),
        )

        assert balance == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_exact_limit_passes(self):
        """Should pass when resulting balance equals exactly the credit limit."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = Decimal("700.00")
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)
        balance = await service.validate_credit_limit(
            customer_id=uuid.uuid4(),
            amount=Decimal("300.00"),
            credit_limit=Decimal("1000.00"),
        )

        assert balance == Decimal("700.00")

    @pytest.mark.asyncio
    async def test_exceeds_limit_raises(self):
        """Should raise CreditLimitExceededError when limit would be exceeded."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = Decimal("800.00")
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)

        with pytest.raises(CreditLimitExceededError) as exc_info:
            await service.validate_credit_limit(
                customer_id=uuid.uuid4(),
                amount=Decimal("300.00"),
                credit_limit=Decimal("1000.00"),
            )

        assert exc_info.value.current_balance == Decimal("800.00")
        assert exc_info.value.attempted_amount == Decimal("300.00")
        assert exc_info.value.credit_limit == Decimal("1000.00")


class TestCreditLedgerServiceRecordDebit:
    """Tests for CreditLedgerService.record_debit."""

    @pytest.mark.asyncio
    async def test_record_debit_creates_entry(self):
        """record_debit should add a positive amount entry to the session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        service = CreditLedgerService(db)
        customer_id = uuid.uuid4()
        reference_id = uuid.uuid4()
        created_by = uuid.uuid4()

        entry = await service.record_debit(
            customer_id=customer_id,
            amount=Decimal("500.00"),
            reference_type="sale",
            reference_id=reference_id,
            created_by=created_by,
        )

        assert entry.customer_id == customer_id
        assert entry.amount == Decimal("500.00")
        assert entry.transaction_type == CreditTransactionType.SALE.value
        assert entry.reference_type == "sale"
        assert entry.reference_id == reference_id
        assert entry.created_by == created_by
        db.add.assert_called_once_with(entry)
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_debit_with_credit_limit_validation(self):
        """record_debit with credit_limit should validate before recording."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = Decimal("200.00")
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)

        entry = await service.record_debit(
            customer_id=uuid.uuid4(),
            amount=Decimal("500.00"),
            reference_type="sale",
            reference_id=uuid.uuid4(),
            created_by=uuid.uuid4(),
            credit_limit=Decimal("1000.00"),
        )

        assert entry.amount == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_record_debit_exceeds_limit_raises(self):
        """record_debit should raise when credit limit would be exceeded."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = Decimal("900.00")
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)

        with pytest.raises(CreditLimitExceededError):
            await service.record_debit(
                customer_id=uuid.uuid4(),
                amount=Decimal("200.00"),
                reference_type="sale",
                reference_id=uuid.uuid4(),
                created_by=uuid.uuid4(),
                credit_limit=Decimal("1000.00"),
            )

        # Should NOT have added entry to session
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_debit_rejects_zero_amount(self):
        """record_debit should raise ValueError for zero amount."""
        db = AsyncMock()
        service = CreditLedgerService(db)

        with pytest.raises(ValueError, match="Debit amount must be positive"):
            await service.record_debit(
                customer_id=uuid.uuid4(),
                amount=Decimal("0"),
                reference_type="sale",
                reference_id=uuid.uuid4(),
                created_by=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_record_debit_rejects_negative_amount(self):
        """record_debit should raise ValueError for negative amount."""
        db = AsyncMock()
        service = CreditLedgerService(db)

        with pytest.raises(ValueError, match="Debit amount must be positive"):
            await service.record_debit(
                customer_id=uuid.uuid4(),
                amount=Decimal("-100.00"),
                reference_type="sale",
                reference_id=uuid.uuid4(),
                created_by=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_record_debit_with_adjustment_type(self):
        """record_debit should support ADJUSTMENT transaction type."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = Decimal("100.00")
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)

        entry = await service.record_debit(
            customer_id=uuid.uuid4(),
            amount=Decimal("50.00"),
            reference_type="adjustment",
            reference_id=uuid.uuid4(),
            created_by=uuid.uuid4(),
            transaction_type=CreditTransactionType.ADJUSTMENT,
            notes="Late fee applied",
            credit_limit=Decimal("1000.00"),
        )

        assert entry.transaction_type == CreditTransactionType.ADJUSTMENT.value
        assert entry.notes == "Late fee applied"


class TestCreditLedgerServiceRecordCredit:
    """Tests for CreditLedgerService.record_credit."""

    @pytest.mark.asyncio
    async def test_record_credit_creates_negative_entry(self):
        """record_credit should store amount as negative (credit reduces balance)."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        service = CreditLedgerService(db)
        customer_id = uuid.uuid4()
        reference_id = uuid.uuid4()
        created_by = uuid.uuid4()

        entry = await service.record_credit(
            customer_id=customer_id,
            amount=Decimal("300.00"),
            reference_type="payment",
            reference_id=reference_id,
            created_by=created_by,
        )

        assert entry.customer_id == customer_id
        assert entry.amount == Decimal("-300.00")  # Stored as negative
        assert entry.transaction_type == CreditTransactionType.PAYMENT.value
        assert entry.reference_type == "payment"
        db.add.assert_called_once_with(entry)
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_credit_return_type(self):
        """record_credit should support RETURN transaction type."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        service = CreditLedgerService(db)

        entry = await service.record_credit(
            customer_id=uuid.uuid4(),
            amount=Decimal("150.00"),
            reference_type="return",
            reference_id=uuid.uuid4(),
            created_by=uuid.uuid4(),
            transaction_type=CreditTransactionType.RETURN,
        )

        assert entry.amount == Decimal("-150.00")
        assert entry.transaction_type == CreditTransactionType.RETURN.value

    @pytest.mark.asyncio
    async def test_record_credit_rejects_zero_amount(self):
        """record_credit should raise ValueError for zero amount."""
        db = AsyncMock()
        service = CreditLedgerService(db)

        with pytest.raises(ValueError, match="Credit amount must be positive"):
            await service.record_credit(
                customer_id=uuid.uuid4(),
                amount=Decimal("0"),
                reference_type="payment",
                reference_id=uuid.uuid4(),
                created_by=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_record_credit_rejects_negative_amount(self):
        """record_credit should raise ValueError for negative amount."""
        db = AsyncMock()
        service = CreditLedgerService(db)

        with pytest.raises(ValueError, match="Credit amount must be positive"):
            await service.record_credit(
                customer_id=uuid.uuid4(),
                amount=Decimal("-50.00"),
                reference_type="payment",
                reference_id=uuid.uuid4(),
                created_by=uuid.uuid4(),
            )


class TestCreditLedgerServiceAgingAnalysis:
    """Tests for CreditLedgerService.aging_analysis."""

    def _make_entry(
        self,
        amount: Decimal,
        created_at: datetime,
        transaction_type: str = CreditTransactionType.SALE.value,
    ) -> MagicMock:
        """Helper to create a mock ledger entry."""
        entry = MagicMock()
        entry.amount = amount
        entry.created_at = created_at
        entry.transaction_type = transaction_type
        return entry

    @pytest.mark.asyncio
    async def test_aging_empty_ledger(self):
        """Aging analysis with no entries should return all zeros."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)
        result = await service.aging_analysis(uuid.uuid4())

        assert result["current"] == Decimal("0.00")
        assert result["1_30_days"] == Decimal("0.00")
        assert result["31_60_days"] == Decimal("0.00")
        assert result["61_90_days"] == Decimal("0.00")
        assert result["over_90_days"] == Decimal("0.00")
        assert result["total"] == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_aging_single_current_debit(self):
        """A debit from today should appear in 'current' bucket."""
        now = datetime.now(timezone.utc)
        entries = [
            self._make_entry(Decimal("500.00"), now),
        ]

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = entries
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)
        result = await service.aging_analysis(uuid.uuid4(), as_of_date=now)

        assert result["current"] == Decimal("500.00")
        assert result["total"] == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_aging_buckets_distribute_correctly(self):
        """Debits should be placed in correct aging buckets based on age."""
        now = datetime.now(timezone.utc)

        entries = [
            self._make_entry(Decimal("100.00"), now - timedelta(days=95)),  # over 90
            self._make_entry(Decimal("200.00"), now - timedelta(days=75)),  # 61-90
            self._make_entry(Decimal("300.00"), now - timedelta(days=45)),  # 31-60
            self._make_entry(Decimal("400.00"), now - timedelta(days=15)),  # 1-30
            self._make_entry(Decimal("500.00"), now),                       # current
        ]

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = entries
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)
        result = await service.aging_analysis(uuid.uuid4(), as_of_date=now)

        assert result["current"] == Decimal("500.00")
        assert result["1_30_days"] == Decimal("400.00")
        assert result["31_60_days"] == Decimal("300.00")
        assert result["61_90_days"] == Decimal("200.00")
        assert result["over_90_days"] == Decimal("100.00")
        assert result["total"] == Decimal("1500.00")

    @pytest.mark.asyncio
    async def test_aging_credits_reduce_oldest_first(self):
        """Credits (payments) should reduce the oldest outstanding debits first."""
        now = datetime.now(timezone.utc)

        entries = [
            # Oldest debit: 100 days ago (over 90)
            self._make_entry(Decimal("500.00"), now - timedelta(days=100)),
            # Newer debit: 20 days ago (1-30)
            self._make_entry(Decimal("300.00"), now - timedelta(days=20)),
            # Payment: 5 days ago (reduces oldest first)
            self._make_entry(Decimal("-400.00"), now - timedelta(days=5)),
        ]

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = entries
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)
        result = await service.aging_analysis(uuid.uuid4(), as_of_date=now)

        # Payment of 400 reduces the oldest 500 debit to 100 remaining
        assert result["over_90_days"] == Decimal("100.00")
        assert result["1_30_days"] == Decimal("300.00")
        assert result["total"] == Decimal("400.00")

    @pytest.mark.asyncio
    async def test_aging_full_payment_zeros_all(self):
        """Full payment should result in all-zero aging buckets."""
        now = datetime.now(timezone.utc)

        entries = [
            self._make_entry(Decimal("1000.00"), now - timedelta(days=50)),
            self._make_entry(Decimal("-1000.00"), now - timedelta(days=5)),
        ]

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = entries
        db.execute.return_value = result_mock

        service = CreditLedgerService(db)
        result = await service.aging_analysis(uuid.uuid4(), as_of_date=now)

        assert result["total"] == Decimal("0.00")
        assert result["current"] == Decimal("0.00")
        assert result["31_60_days"] == Decimal("0.00")
