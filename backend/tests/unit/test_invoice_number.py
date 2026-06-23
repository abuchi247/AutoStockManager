"""Unit tests for the sequential invoice number generator.

Tests validate:
1. Invoice numbers follow the format INV-{year}-{sequential_number:06d}
2. Sequential numbers increase monotonically
3. The generator uses PostgreSQL's nextval() for thread safety
4. The current year is embedded in the invoice number

Satisfies Requirement 5.5: WHEN a sale is confirmed, THE Invoice_Manager
SHALL generate a unique sequential invoice number for the transaction.
"""

import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.invoice_number import (
    INVOICE_NUMBER_SEQUENCE,
    generate_invoice_number,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    return db


def _mock_db_nextval(mock_db, seq_value: int):
    """Configure mock_db.execute to return a given sequence value."""
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = seq_value
    mock_db.execute = AsyncMock(return_value=mock_result)


# =============================================================================
# Test Class: Invoice Number Format
# =============================================================================


class TestInvoiceNumberFormat:
    """Tests for the invoice number format."""

    @pytest.mark.asyncio
    async def test_format_matches_pattern(self, mock_db):
        """Invoice number should match INV-YYYY-NNNNNN pattern."""
        _mock_db_nextval(mock_db, 1)

        result = await generate_invoice_number(mock_db)

        pattern = r"^INV-\d{4}-\d{6}$"
        assert re.match(pattern, result), f"'{result}' does not match expected format"

    @pytest.mark.asyncio
    async def test_includes_current_year(self, mock_db):
        """Invoice number should include the current UTC year."""
        _mock_db_nextval(mock_db, 42)

        result = await generate_invoice_number(mock_db)

        current_year = datetime.now(timezone.utc).year
        assert f"INV-{current_year}-" in result

    @pytest.mark.asyncio
    async def test_sequential_number_zero_padded_to_six_digits(self, mock_db):
        """Sequential number should be zero-padded to 6 digits."""
        _mock_db_nextval(mock_db, 1)

        result = await generate_invoice_number(mock_db)

        # Extract the sequential part
        parts = result.split("-")
        sequential_part = parts[2]
        assert sequential_part == "000001"
        assert len(sequential_part) == 6

    @pytest.mark.asyncio
    async def test_large_sequence_number(self, mock_db):
        """Should handle sequence numbers larger than 6 digits."""
        _mock_db_nextval(mock_db, 1234567)

        result = await generate_invoice_number(mock_db)

        current_year = datetime.now(timezone.utc).year
        assert result == f"INV-{current_year}-1234567"

    @pytest.mark.asyncio
    async def test_sequence_value_one(self, mock_db):
        """First invoice should be INV-YYYY-000001."""
        _mock_db_nextval(mock_db, 1)

        result = await generate_invoice_number(mock_db)

        current_year = datetime.now(timezone.utc).year
        assert result == f"INV-{current_year}-000001"

    @pytest.mark.asyncio
    async def test_sequence_value_999999(self, mock_db):
        """Should handle max 6-digit value correctly."""
        _mock_db_nextval(mock_db, 999999)

        result = await generate_invoice_number(mock_db)

        current_year = datetime.now(timezone.utc).year
        assert result == f"INV-{current_year}-999999"


# =============================================================================
# Test Class: Sequential Behavior
# =============================================================================


class TestInvoiceNumberSequential:
    """Tests for sequential invoice number generation."""

    @pytest.mark.asyncio
    async def test_consecutive_calls_produce_increasing_numbers(self, mock_db):
        """Consecutive calls should produce monotonically increasing numbers."""
        results = []
        for seq_val in [1, 2, 3, 4, 5]:
            _mock_db_nextval(mock_db, seq_val)
            result = await generate_invoice_number(mock_db)
            results.append(result)

        # Extract sequential numbers and verify ordering
        seq_numbers = [int(r.split("-")[2]) for r in results]
        assert seq_numbers == [1, 2, 3, 4, 5]
        assert seq_numbers == sorted(seq_numbers)

    @pytest.mark.asyncio
    async def test_each_call_produces_unique_number(self, mock_db):
        """Each call should produce a unique invoice number."""
        results = set()
        for seq_val in range(1, 11):
            _mock_db_nextval(mock_db, seq_val)
            result = await generate_invoice_number(mock_db)
            results.add(result)

        assert len(results) == 10


# =============================================================================
# Test Class: Database Interaction
# =============================================================================


class TestInvoiceNumberDatabaseInteraction:
    """Tests for database sequence interaction."""

    @pytest.mark.asyncio
    async def test_calls_nextval_on_correct_sequence(self, mock_db):
        """Should call nextval on the invoice_number_seq sequence."""
        _mock_db_nextval(mock_db, 1)

        await generate_invoice_number(mock_db)

        # Verify execute was called with the correct SQL
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        sql_text = str(call_args[0][0].text)
        assert "nextval" in sql_text
        assert INVOICE_NUMBER_SEQUENCE in sql_text

    @pytest.mark.asyncio
    async def test_uses_invoice_number_seq_constant(self, mock_db):
        """The sequence name constant should be 'invoice_number_seq'."""
        assert INVOICE_NUMBER_SEQUENCE == "invoice_number_seq"


# =============================================================================
# Test Class: Integration with confirm_sale
# =============================================================================


class TestConfirmSaleInvoiceNumber:
    """Tests verifying confirm_sale uses the sequential generator."""

    @pytest.mark.asyncio
    @patch("app.services.sales_service.generate_invoice_number", new_callable=AsyncMock)
    @patch("app.services.sales_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.sales_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_confirm_sale_uses_sequential_invoice_number(
        self, mock_fifo, mock_record, mock_gen_invoice
    ):
        """confirm_sale should call generate_invoice_number for the invoice."""
        from decimal import Decimal
        import uuid

        from app.models.sale import Sale, SaleItem, SaleStatus, PaymentType
        from app.models.stock_status_cache import StockStatusCache
        from app.services.sales_service import SalesService

        # Setup
        mock_gen_invoice.return_value = "INV-2024-000042"
        mock_fifo.return_value = (Decimal("100.00"), [])

        sale_id = uuid.uuid4()
        location_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()

        sale_item = SaleItem(
            sale_id=sale_id,
            spare_part_id=spare_part_id,
            quantity=Decimal("2.00"),
            unit_price=Decimal("50.00"),
            discount_amount=Decimal("0.00"),
            line_total=Decimal("100.00"),
        )
        sale_item.id = uuid.uuid4()

        sale = Sale(
            customer_id=uuid.uuid4(),
            location_id=location_id,
            status=SaleStatus.DRAFT,
            payment_type=PaymentType.CASH,
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            discount_total=Decimal("0.00"),
        )
        sale.id = sale_id
        sale.items = [sale_item]

        # Mock db
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        # Mock sale lookup
        mock_sale_result = MagicMock()
        mock_sale_result.scalar_one_or_none.return_value = sale

        # Mock stock cache lookup (for SELECT FOR UPDATE)
        mock_cache = StockStatusCache(
            spare_part_id=spare_part_id,
            location_id=location_id,
            current_quantity=Decimal("10.00"),
        )
        mock_cache_result = MagicMock()
        mock_cache_result.scalar_one_or_none.return_value = mock_cache

        # First execute call = sale lookup, second = stock cache
        mock_db.execute = AsyncMock(
            side_effect=[mock_sale_result, mock_cache_result]
        )

        service = SalesService(mock_db, user_id=uuid.uuid4())
        result = await service.confirm_sale(sale_id)

        # Verify the sequential generator was called
        mock_gen_invoice.assert_called_once_with(mock_db)
        assert result.invoice_number == "INV-2024-000042"
