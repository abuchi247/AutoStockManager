"""Unit tests for the SalesService.create_sale and confirm_sale methods.

Tests cover:
- Sale creation (create_sale)
- Sale confirmation with pessimistic locking and FIFO COGS (confirm_sale)
- Line total calculation: (quantity × unit_price) - discount_amount
- Insufficient stock rejection
- Status validation
- Invoice number generation

Satisfies Requirements: 5.2, 5.6, 5.7, 5.9, 5.10, 5.11
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.sale import Sale, SaleItem, SaleStatus, PaymentType
from app.models.stock_status_cache import StockStatusCache
from app.services.sales_service import (
    SalesService,
    SaleNotFoundError,
    InvalidSaleStatusError,
    InsufficientStockError,
    SaleHasNoItemsError,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_sale_item(
    spare_part_id: uuid.UUID = None,
    quantity: Decimal = Decimal("5"),
    unit_price: Decimal = Decimal("100.00"),
    discount_amount: Decimal = Decimal("0.00"),
) -> SaleItem:
    """Create a SaleItem for testing."""
    item = SaleItem(
        spare_part_id=spare_part_id or uuid.uuid4(),
        quantity=quantity,
        unit_price=unit_price,
        discount_amount=discount_amount,
        line_total=(quantity * unit_price) - discount_amount,
    )
    item.id = uuid.uuid4()
    item.sale_id = uuid.uuid4()
    return item


def _make_sale(
    sale_id: uuid.UUID = None,
    location_id: uuid.UUID = None,
    status: SaleStatus = SaleStatus.DRAFT,
    payment_type: PaymentType = PaymentType.CASH,
    items: list = None,
) -> Sale:
    """Create a Sale for testing."""
    sale = Sale(
        customer_id=None,
        location_id=location_id or uuid.uuid4(),
        status=status,
        payment_type=payment_type,
        subtotal=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("0.00"),
        discount_total=Decimal("0.00"),
    )
    sale.id = sale_id or uuid.uuid4()
    sale.items = items if items is not None else []
    return sale


def _make_cache(
    spare_part_id: uuid.UUID,
    location_id: uuid.UUID,
    current_quantity: Decimal = Decimal("100"),
) -> StockStatusCache:
    """Create a StockStatusCache row for testing."""
    cache = StockStatusCache(
        spare_part_id=spare_part_id,
        location_id=location_id,
        current_quantity=current_quantity,
    )
    cache.id = uuid.uuid4()
    return cache


# =============================================================================
# Test: create_sale
# =============================================================================


class TestCreateSale:
    """Tests for SalesService.create_sale."""

    async def test_create_sale_basic(self):
        """create_sale should create a sale in DRAFT status."""
        db = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()

        service = SalesService(db=db, user_id=uuid.uuid4())
        location_id = uuid.uuid4()

        sale = await service.create_sale(
            customer_id=None,
            location_id=location_id,
            payment_type=PaymentType.CASH,
        )

        assert sale.status == SaleStatus.DRAFT
        assert sale.location_id == location_id
        assert sale.payment_type == PaymentType.CASH
        db.add.assert_called_once()

    async def test_create_sale_with_customer(self):
        """create_sale should associate with a customer when provided."""
        db = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()

        service = SalesService(db=db, user_id=uuid.uuid4())
        customer_id = uuid.uuid4()

        sale = await service.create_sale(
            customer_id=customer_id,
            location_id=uuid.uuid4(),
            payment_type=PaymentType.CREDIT,
        )

        assert sale.customer_id == customer_id
        assert sale.payment_type == PaymentType.CREDIT

    async def test_create_sale_line_total_calculation(self):
        """Line total should be (quantity × unit_price) - discount_amount."""
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        # Track what gets added to the db
        added_items = []

        def track_add(obj):
            if isinstance(obj, SaleItem):
                added_items.append(obj)

        db.add = track_add

        service = SalesService(db=db, user_id=uuid.uuid4())

        await service.create_sale(
            customer_id=None,
            location_id=uuid.uuid4(),
            items=[
                {
                    "spare_part_id": uuid.uuid4(),
                    "quantity": "4",
                    "unit_price": "200.00",
                    "discount_amount": "50.00",
                }
            ],
        )

        assert len(added_items) == 1
        item = added_items[0]
        # line_total = (4 × 200.00) - 50.00 = 750.00
        assert item.line_total == Decimal("750.00")

    async def test_create_sale_zero_discount(self):
        """Line total with zero discount should equal quantity * unit_price."""
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        added_items = []

        def track_add(obj):
            if isinstance(obj, SaleItem):
                added_items.append(obj)

        db.add = track_add

        service = SalesService(db=db, user_id=uuid.uuid4())

        await service.create_sale(
            customer_id=None,
            location_id=uuid.uuid4(),
            items=[
                {
                    "spare_part_id": uuid.uuid4(),
                    "quantity": "2",
                    "unit_price": "300.00",
                }
            ],
        )

        assert len(added_items) == 1
        # line_total = (2 × 300.00) - 0.00 = 600.00
        assert added_items[0].line_total == Decimal("600.00")

    async def test_create_sale_multiple_items(self):
        """create_sale should correctly compute line_total for each item."""
        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        added_items = []

        def track_add(obj):
            if isinstance(obj, SaleItem):
                added_items.append(obj)

        db.add = track_add

        service = SalesService(db=db, user_id=uuid.uuid4())

        await service.create_sale(
            customer_id=None,
            location_id=uuid.uuid4(),
            items=[
                {
                    "spare_part_id": uuid.uuid4(),
                    "quantity": "3",
                    "unit_price": "100.00",
                    "discount_amount": "10.00",
                },
                {
                    "spare_part_id": uuid.uuid4(),
                    "quantity": "1",
                    "unit_price": "500.00",
                    "discount_amount": "0.00",
                },
            ],
        )

        assert len(added_items) == 2
        # item1: (3 × 100) - 10 = 290
        assert added_items[0].line_total == Decimal("290.00")
        # item2: (1 × 500) - 0 = 500
        assert added_items[1].line_total == Decimal("500.00")


# =============================================================================
# Test: confirm_sale
# =============================================================================


class TestConfirmSale:
    """Tests for SalesService.confirm_sale."""

    async def test_confirm_sale_not_found(self):
        """confirm_sale should raise SaleNotFoundError when sale doesn't exist."""
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        service = SalesService(db=db, user_id=uuid.uuid4())
        with pytest.raises(SaleNotFoundError):
            await service.confirm_sale(uuid.uuid4())

    async def test_confirm_sale_wrong_status(self):
        """confirm_sale should reject non-DRAFT sales."""
        sale = _make_sale(status=SaleStatus.CONFIRMED)

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = sale
        db.execute = AsyncMock(return_value=result)

        service = SalesService(db=db, user_id=uuid.uuid4())
        with pytest.raises(InvalidSaleStatusError) as exc_info:
            await service.confirm_sale(sale.id)

        assert exc_info.value.current_status == SaleStatus.CONFIRMED.value
        assert exc_info.value.expected_status == SaleStatus.DRAFT.value

    async def test_confirm_sale_no_items(self):
        """confirm_sale should reject sales with no items."""
        sale = _make_sale(items=[])

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = sale
        db.execute = AsyncMock(return_value=result)

        service = SalesService(db=db, user_id=uuid.uuid4())
        with pytest.raises(SaleHasNoItemsError):
            await service.confirm_sale(sale.id)

    async def test_confirm_sale_insufficient_stock(self):
        """confirm_sale should raise InsufficientStockError when stock is low."""
        location_id = uuid.uuid4()
        part_id = uuid.uuid4()
        item = _make_sale_item(spare_part_id=part_id, quantity=Decimal("10"))
        sale = _make_sale(location_id=location_id, items=[item])

        # Cache has only 5 units
        cache = _make_cache(
            spare_part_id=part_id,
            location_id=location_id,
            current_quantity=Decimal("5"),
        )

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = sale
            else:
                result.scalar_one_or_none.return_value = cache
            return result

        db = AsyncMock()
        db.execute = mock_execute
        db.flush = AsyncMock()

        service = SalesService(db=db, user_id=uuid.uuid4())
        with pytest.raises(InsufficientStockError) as exc_info:
            await service.confirm_sale(sale.id)

        assert exc_info.value.spare_part_id == part_id
        assert exc_info.value.requested == Decimal("10")
        assert exc_info.value.available == Decimal("5")

    async def test_confirm_sale_no_cache_row_means_zero_stock(self):
        """confirm_sale should treat missing cache as zero stock."""
        location_id = uuid.uuid4()
        part_id = uuid.uuid4()
        item = _make_sale_item(spare_part_id=part_id, quantity=Decimal("1"))
        sale = _make_sale(location_id=location_id, items=[item])

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = sale
            else:
                result.scalar_one_or_none.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute
        db.flush = AsyncMock()

        service = SalesService(db=db, user_id=uuid.uuid4())
        with pytest.raises(InsufficientStockError) as exc_info:
            await service.confirm_sale(sale.id)

        assert exc_info.value.available == Decimal("0")

    @patch("app.services.sales_service.consume_fifo_layers")
    @patch("app.services.sales_service.record_inventory_movement")
    async def test_confirm_sale_success(
        self, mock_record_movement, mock_consume_fifo
    ):
        """confirm_sale should confirm a DRAFT sale with sufficient stock."""
        location_id = uuid.uuid4()
        part_id = uuid.uuid4()
        user_id = uuid.uuid4()

        item = _make_sale_item(
            spare_part_id=part_id,
            quantity=Decimal("3"),
            unit_price=Decimal("100.00"),
            discount_amount=Decimal("10.00"),
        )
        sale = _make_sale(location_id=location_id, items=[item])

        cache = _make_cache(
            spare_part_id=part_id,
            location_id=location_id,
            current_quantity=Decimal("50"),
        )

        mock_consume_fifo.return_value = (Decimal("240.00"), [
            {"layer_id": uuid.uuid4(), "quantity_consumed": Decimal("3"),
             "unit_cost": Decimal("80.00"), "layer_cost": Decimal("240.00")}
        ])
        mock_record_movement.return_value = MagicMock()

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = sale
            else:
                result.scalar_one_or_none.return_value = cache
            return result

        db = AsyncMock()
        db.execute = mock_execute
        db.flush = AsyncMock()

        service = SalesService(db=db, user_id=user_id)
        confirmed = await service.confirm_sale(sale.id)

        # Status should be CONFIRMED
        assert confirmed.status == SaleStatus.CONFIRMED

        # COGS should be set on item
        assert item.cost_of_goods_sold == Decimal("240.00")

        # Line total recalculated: (3 × 100.00) - 10.00 = 290.00
        assert item.line_total == Decimal("290.00")

        # Subtotal = sum of line_totals
        assert confirmed.subtotal == Decimal("290.00")

        # Invoice number should be generated
        assert confirmed.invoice_number is not None
        assert confirmed.invoice_number.startswith("INV-")

        # FIFO was called with correct args
        mock_consume_fifo.assert_called_once_with(
            db=db,
            spare_part_id=part_id,
            location_id=location_id,
            quantity_to_consume=Decimal("3"),
        )

        # Ledger movement was recorded with SALE type and negative qty
        mock_record_movement.assert_called_once()
        call_kwargs = mock_record_movement.call_args.kwargs
        assert call_kwargs["movement_type"] == "SALE"
        assert call_kwargs["quantity_change"] == Decimal("-3")
        assert call_kwargs["reference_type"] == "sale"
        assert call_kwargs["reference_id"] == sale.id

    @patch("app.services.sales_service.consume_fifo_layers")
    @patch("app.services.sales_service.record_inventory_movement")
    async def test_confirm_sale_multiple_items(
        self, mock_record_movement, mock_consume_fifo
    ):
        """confirm_sale should process multiple items and sum totals correctly."""
        location_id = uuid.uuid4()
        user_id = uuid.uuid4()

        part_id_1 = uuid.uuid4()
        part_id_2 = uuid.uuid4()

        item1 = _make_sale_item(
            spare_part_id=part_id_1,
            quantity=Decimal("2"),
            unit_price=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
        )
        item2 = _make_sale_item(
            spare_part_id=part_id_2,
            quantity=Decimal("5"),
            unit_price=Decimal("50.00"),
            discount_amount=Decimal("25.00"),
        )
        sale = _make_sale(location_id=location_id, items=[item1, item2])

        cache1 = _make_cache(
            spare_part_id=part_id_1,
            location_id=location_id,
            current_quantity=Decimal("100"),
        )
        cache2 = _make_cache(
            spare_part_id=part_id_2,
            location_id=location_id,
            current_quantity=Decimal("100"),
        )

        mock_consume_fifo.side_effect = [
            (Decimal("160.00"), []),  # item1: 2 × 80
            (Decimal("200.00"), []),  # item2: 5 × 40
        ]
        mock_record_movement.return_value = MagicMock()

        call_count = {"n": 0}
        caches = [cache1, cache2]

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = sale
            else:
                cache_idx = call_count["n"] - 2
                if cache_idx < len(caches):
                    result.scalar_one_or_none.return_value = caches[cache_idx]
                else:
                    result.scalar_one_or_none.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute
        db.flush = AsyncMock()

        service = SalesService(db=db, user_id=user_id)
        confirmed = await service.confirm_sale(sale.id)

        # item1 line_total: (2 × 100) - 0 = 200
        assert item1.line_total == Decimal("200.00")
        # item2 line_total: (5 × 50) - 25 = 225
        assert item2.line_total == Decimal("225.00")

        # Subtotal = 200 + 225 = 425
        assert confirmed.subtotal == Decimal("425.00")

        # Discount total = 0 + 25 = 25
        assert confirmed.discount_total == Decimal("25.00")

        # COGS set on each item
        assert item1.cost_of_goods_sold == Decimal("160.00")
        assert item2.cost_of_goods_sold == Decimal("200.00")

        # Ledger movement called twice (once per item)
        assert mock_record_movement.call_count == 2

    @patch("app.services.sales_service.consume_fifo_layers")
    @patch("app.services.sales_service.record_inventory_movement")
    async def test_confirm_sale_credit_payment_type(
        self, mock_record_movement, mock_consume_fifo
    ):
        """confirm_sale with CREDIT payment should succeed (credit placeholder)."""
        location_id = uuid.uuid4()
        part_id = uuid.uuid4()

        item = _make_sale_item(
            spare_part_id=part_id,
            quantity=Decimal("1"),
            unit_price=Decimal("500.00"),
        )
        sale = _make_sale(
            location_id=location_id,
            payment_type=PaymentType.CREDIT,
            items=[item],
        )
        sale.customer_id = uuid.uuid4()

        cache = _make_cache(
            spare_part_id=part_id,
            location_id=location_id,
            current_quantity=Decimal("10"),
        )

        mock_consume_fifo.return_value = (Decimal("350.00"), [])
        mock_record_movement.return_value = MagicMock()

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = sale
            else:
                result.scalar_one_or_none.return_value = cache
            return result

        db = AsyncMock()
        db.execute = mock_execute
        db.flush = AsyncMock()

        service = SalesService(db=db, user_id=uuid.uuid4())
        confirmed = await service.confirm_sale(sale.id)

        assert confirmed.status == SaleStatus.CONFIRMED
        assert confirmed.payment_type == PaymentType.CREDIT

    @patch("app.services.sales_service.consume_fifo_layers")
    @patch("app.services.sales_service.record_inventory_movement")
    async def test_confirm_sale_sets_invoice_number(
        self, mock_record_movement, mock_consume_fifo
    ):
        """confirm_sale should generate an invoice number starting with INV-."""
        location_id = uuid.uuid4()
        part_id = uuid.uuid4()

        item = _make_sale_item(spare_part_id=part_id, quantity=Decimal("1"))
        sale = _make_sale(location_id=location_id, items=[item])

        cache = _make_cache(
            spare_part_id=part_id,
            location_id=location_id,
            current_quantity=Decimal("10"),
        )

        mock_consume_fifo.return_value = (Decimal("50.00"), [])
        mock_record_movement.return_value = MagicMock()

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = sale
            else:
                result.scalar_one_or_none.return_value = cache
            return result

        db = AsyncMock()
        db.execute = mock_execute
        db.flush = AsyncMock()

        service = SalesService(db=db, user_id=uuid.uuid4())
        confirmed = await service.confirm_sale(sale.id)

        assert confirmed.invoice_number is not None
        assert confirmed.invoice_number.startswith("INV-")

    @patch("app.services.sales_service.consume_fifo_layers")
    @patch("app.services.sales_service.record_inventory_movement")
    async def test_confirm_sale_unit_cost_in_ledger(
        self, mock_record_movement, mock_consume_fifo
    ):
        """confirm_sale should record weighted avg unit_cost in ledger entry."""
        location_id = uuid.uuid4()
        part_id = uuid.uuid4()

        item = _make_sale_item(
            spare_part_id=part_id,
            quantity=Decimal("4"),
            unit_price=Decimal("200.00"),
        )
        sale = _make_sale(location_id=location_id, items=[item])

        cache = _make_cache(
            spare_part_id=part_id,
            location_id=location_id,
            current_quantity=Decimal("20"),
        )

        # COGS = 400 for 4 units → avg unit_cost = 100
        mock_consume_fifo.return_value = (Decimal("400.00"), [])
        mock_record_movement.return_value = MagicMock()

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = sale
            else:
                result.scalar_one_or_none.return_value = cache
            return result

        db = AsyncMock()
        db.execute = mock_execute
        db.flush = AsyncMock()

        service = SalesService(db=db, user_id=uuid.uuid4())
        await service.confirm_sale(sale.id)

        call_kwargs = mock_record_movement.call_args.kwargs
        # unit_cost = total_cogs / quantity = 400 / 4 = 100
        assert call_kwargs["unit_cost"] == Decimal("100.00")


# =============================================================================
# Test: line_total calculation edge cases
# =============================================================================


class TestLineTotalCalculation:
    """Tests for line_total formula: (quantity × unit_price) - discount_amount."""

    def test_basic_line_total(self):
        """5 × 100 - 0 = 500."""
        item = _make_sale_item(
            quantity=Decimal("5"),
            unit_price=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
        )
        assert item.line_total == Decimal("500.00")

    def test_line_total_with_discount(self):
        """3 × 200 - 50 = 550."""
        item = _make_sale_item(
            quantity=Decimal("3"),
            unit_price=Decimal("200.00"),
            discount_amount=Decimal("50.00"),
        )
        assert item.line_total == Decimal("550.00")

    def test_line_total_fractional_quantity(self):
        """2.5 × 40 - 5 = 95."""
        item = _make_sale_item(
            quantity=Decimal("2.5"),
            unit_price=Decimal("40.00"),
            discount_amount=Decimal("5.00"),
        )
        assert item.line_total == Decimal("95.00")

    def test_line_total_single_unit_no_discount(self):
        """1 × 250.50 - 0 = 250.50."""
        item = _make_sale_item(
            quantity=Decimal("1"),
            unit_price=Decimal("250.50"),
            discount_amount=Decimal("0.00"),
        )
        assert item.line_total == Decimal("250.50")

    def test_line_total_large_discount(self):
        """1 × 100 - 99 = 1."""
        item = _make_sale_item(
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            discount_amount=Decimal("99.00"),
        )
        assert item.line_total == Decimal("1.00")
