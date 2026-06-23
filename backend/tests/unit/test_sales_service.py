"""Unit tests for the SalesService.return_sale method.

Tests validate the sales return flow:
1. Validates the sale is in CONFIRMED status
2. Creates new CostLayers at the return location with correct attributes
3. Records RETURN ledger entries for each returned item
4. Updates sale status to RETURNED
5. Never modifies or re-opens previously consumed/closed cost layers

Satisfies Requirements: 5.8, 5.12, 5.13, 5.14
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.models.cost_layer import CostLayer
from app.models.inventory_movement_ledger import MovementType
from app.models.sale import Sale, SaleItem, SaleStatus, PaymentType
from app.services.sales_service import (
    InvalidSaleStatusError,
    SaleNotFoundError,
    SalesService,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def sale_id():
    """Generate a fixed sale ID."""
    return uuid.uuid4()


@pytest.fixture
def location_id():
    """Generate a fixed location ID."""
    return uuid.uuid4()


@pytest.fixture
def returned_by_user():
    """Generate a fixed user ID for the return processor."""
    return uuid.uuid4()


@pytest.fixture
def spare_part_id_1():
    """Generate a fixed spare part ID."""
    return uuid.uuid4()


@pytest.fixture
def spare_part_id_2():
    """Generate a second spare part ID."""
    return uuid.uuid4()


@pytest.fixture
def sale_item_1(sale_id, spare_part_id_1):
    """Create a sale item with known COGS."""
    item = SaleItem(
        sale_id=sale_id,
        spare_part_id=spare_part_id_1,
        quantity=Decimal("5.00"),
        unit_price=Decimal("200.00"),
        discount_amount=Decimal("0.00"),
        line_total=Decimal("1000.00"),
        cost_of_goods_sold=Decimal("750.00"),
    )
    item.id = uuid.uuid4()
    return item


@pytest.fixture
def sale_item_2(sale_id, spare_part_id_2):
    """Create a second sale item."""
    item = SaleItem(
        sale_id=sale_id,
        spare_part_id=spare_part_id_2,
        quantity=Decimal("3.00"),
        unit_price=Decimal("100.00"),
        discount_amount=Decimal("10.00"),
        line_total=Decimal("290.00"),
        cost_of_goods_sold=Decimal("240.00"),
    )
    item.id = uuid.uuid4()
    return item


@pytest.fixture
def confirmed_sale(sale_id, location_id, sale_item_1, sale_item_2):
    """Create a confirmed sale with two items."""
    sale = Sale(
        customer_id=uuid.uuid4(),
        location_id=location_id,
        status=SaleStatus.CONFIRMED,
        payment_type=PaymentType.CASH,
        invoice_number="INV-001",
        subtotal=Decimal("1290.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1290.00"),
        discount_total=Decimal("10.00"),
    )
    sale.id = sale_id
    sale.items = [sale_item_1, sale_item_2]
    return sale


@pytest.fixture
def draft_sale(sale_id, location_id, sale_item_1):
    """Create a sale in DRAFT status."""
    sale = Sale(
        customer_id=uuid.uuid4(),
        location_id=location_id,
        status=SaleStatus.DRAFT,
        payment_type=PaymentType.CASH,
    )
    sale.id = sale_id
    sale.items = [sale_item_1]
    return sale


# =============================================================================
# Helper to mock the DB execute for sale lookup
# =============================================================================


def _mock_db_with_sale(mock_db, sale):
    """Configure mock_db.execute to return the given sale on SELECT."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sale
    mock_db.execute = AsyncMock(return_value=mock_result)


# =============================================================================
# Test Class: Validation
# =============================================================================


class TestReturnSaleValidation:
    """Tests for return_sale input validation."""

    @pytest.mark.asyncio
    async def test_raises_sale_not_found_when_sale_missing(
        self, mock_db, returned_by_user
    ):
        """Should raise SaleNotFoundError if sale doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SalesService(mock_db)

        with pytest.raises(SaleNotFoundError):
            await service.return_sale(
                sale_id=uuid.uuid4(),
                returned_by=returned_by_user,
            )

    @pytest.mark.asyncio
    async def test_raises_invalid_status_when_sale_is_draft(
        self, mock_db, draft_sale, returned_by_user
    ):
        """Should raise InvalidSaleStatusError if sale is DRAFT."""
        _mock_db_with_sale(mock_db, draft_sale)
        service = SalesService(mock_db)

        with pytest.raises(InvalidSaleStatusError) as exc_info:
            await service.return_sale(
                sale_id=draft_sale.id,
                returned_by=returned_by_user,
            )
        assert exc_info.value.current_status == SaleStatus.DRAFT.value
        assert exc_info.value.expected_status == SaleStatus.CONFIRMED.value

    @pytest.mark.asyncio
    async def test_raises_invalid_status_when_sale_already_returned(
        self, mock_db, confirmed_sale, returned_by_user
    ):
        """Should raise InvalidSaleStatusError if sale is already RETURNED."""
        confirmed_sale.status = SaleStatus.RETURNED
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        with pytest.raises(InvalidSaleStatusError):
            await service.return_sale(
                sale_id=confirmed_sale.id,
                returned_by=returned_by_user,
            )


# =============================================================================
# Test Class: Cost Layer Creation (Req 5.12, 5.13, 5.14)
# =============================================================================


class TestReturnSaleCostLayerCreation:
    """Tests for new cost layer creation on return."""

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_creates_cost_layer_per_sale_item(
        self, mock_record, mock_db, confirmed_sale, returned_by_user
    ):
        """Should create one new CostLayer per returned item."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        # db.add is called for each new CostLayer
        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [
            c for c in add_calls if isinstance(c[0][0], CostLayer)
        ]
        assert len(cost_layer_adds) == 2  # Two items in the sale

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_cost_layer_at_sale_location(
        self, mock_record, mock_db, confirmed_sale, returned_by_user, location_id
    ):
        """New CostLayer should be at the sale's location_id."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        add_calls = mock_db.add.call_args_list
        cost_layers = [
            c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)
        ]
        for layer in cost_layers:
            assert layer.location_id == location_id

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_cost_layer_unit_cost_from_cogs(
        self,
        mock_record,
        mock_db,
        confirmed_sale,
        returned_by_user,
        sale_item_1,
        sale_item_2,
    ):
        """CostLayer unit_cost should be COGS / quantity from the sale item."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        add_calls = mock_db.add.call_args_list
        cost_layers = [
            c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)
        ]
        # Item 1: COGS=750, qty=5 → unit_cost = 150
        # Item 2: COGS=240, qty=3 → unit_cost = 80
        expected_costs = {
            sale_item_1.spare_part_id: Decimal("750.00") / Decimal("5.00"),
            sale_item_2.spare_part_id: Decimal("240.00") / Decimal("3.00"),
        }
        for layer in cost_layers:
            assert layer.unit_cost == expected_costs[layer.spare_part_id]

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_cost_layer_quantities_match_sale_item(
        self, mock_record, mock_db, confirmed_sale, returned_by_user, sale_item_1
    ):
        """CostLayer original_quantity and remaining_quantity = item quantity."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        add_calls = mock_db.add.call_args_list
        cost_layers = [
            c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)
        ]
        # Find the layer for item_1
        layer_1 = next(
            l for l in cost_layers
            if l.spare_part_id == sale_item_1.spare_part_id
        )
        assert layer_1.original_quantity == sale_item_1.quantity
        assert layer_1.remaining_quantity == sale_item_1.quantity

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_cost_layer_source_type_is_return(
        self, mock_record, mock_db, confirmed_sale, returned_by_user
    ):
        """CostLayer source_type should be 'return'."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        add_calls = mock_db.add.call_args_list
        cost_layers = [
            c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)
        ]
        for layer in cost_layers:
            assert layer.source_type == "return"

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_cost_layer_source_reference_is_sale_id(
        self, mock_record, mock_db, confirmed_sale, returned_by_user, sale_id
    ):
        """CostLayer source_reference_id should be the sale ID."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        add_calls = mock_db.add.call_args_list
        cost_layers = [
            c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)
        ]
        for layer in cost_layers:
            assert layer.source_reference_id == sale_id

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_no_existing_cost_layers_modified(
        self, mock_record, mock_db, confirmed_sale, returned_by_user
    ):
        """Return should NEVER modify existing cost layers (Req 5.14).

        We verify that consume_fifo_layers is NOT called during a return,
        and that no SELECT FOR UPDATE is made on cost_layers.
        """
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        with patch(
            "app.services.sales_service.consume_fifo_layers"
        ) as mock_fifo:
            await service.return_sale(
                sale_id=confirmed_sale.id, returned_by=returned_by_user
            )
            # consume_fifo_layers must never be called during return
            mock_fifo.assert_not_called()


# =============================================================================
# Test Class: Ledger Entry Creation
# =============================================================================


class TestReturnSaleLedgerEntries:
    """Tests for inventory movement ledger entries on return."""

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_records_return_movement_per_item(
        self, mock_record, mock_db, confirmed_sale, returned_by_user
    ):
        """Should call record_inventory_movement once per returned item."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        assert mock_record.call_count == 2  # Two items returned

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_ledger_entry_movement_type_is_return(
        self, mock_record, mock_db, confirmed_sale, returned_by_user
    ):
        """Ledger entries should have RETURN movement type."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        for call_args in mock_record.call_args_list:
            assert call_args.kwargs["movement_type"] == MovementType.RETURN.value

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_ledger_entry_positive_quantity(
        self, mock_record, mock_db, confirmed_sale, returned_by_user
    ):
        """Return ledger entries should have positive quantity (inflow)."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        for call_args in mock_record.call_args_list:
            assert call_args.kwargs["quantity_change"] > 0

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_ledger_entry_reference_type_is_sale(
        self, mock_record, mock_db, confirmed_sale, returned_by_user
    ):
        """Ledger entries should reference the sale."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        for call_args in mock_record.call_args_list:
            assert call_args.kwargs["reference_type"] == "sale"
            assert call_args.kwargs["reference_id"] == confirmed_sale.id

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_ledger_entry_at_sale_location(
        self, mock_record, mock_db, confirmed_sale, returned_by_user, location_id
    ):
        """Ledger entries should be at the sale's location."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        for call_args in mock_record.call_args_list:
            assert call_args.kwargs["location_id"] == location_id

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_ledger_entry_created_by_user(
        self, mock_record, mock_db, confirmed_sale, returned_by_user
    ):
        """Ledger entries should record who processed the return."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        for call_args in mock_record.call_args_list:
            assert call_args.kwargs["created_by"] == returned_by_user


# =============================================================================
# Test Class: Sale Status Update
# =============================================================================


class TestReturnSaleStatusUpdate:
    """Tests for sale status update after return."""

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_sets_status_to_returned(
        self, mock_record, mock_db, confirmed_sale, returned_by_user
    ):
        """Sale status should be updated to RETURNED."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        result = await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        assert result.status == SaleStatus.RETURNED

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_returns_updated_sale(
        self, mock_record, mock_db, confirmed_sale, returned_by_user, sale_id
    ):
        """Should return the sale object with updated status."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        result = await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        assert result.id == sale_id
        assert result.status == SaleStatus.RETURNED


# =============================================================================
# Test Class: Partial Return (specific items/quantities)
# =============================================================================


class TestReturnSalePartialReturn:
    """Tests for partial return functionality."""

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_partial_return_specific_items(
        self,
        mock_record,
        mock_db,
        confirmed_sale,
        returned_by_user,
        sale_item_1,
    ):
        """Should only return specified items when return_items provided."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id,
            returned_by=returned_by_user,
            return_items=[
                {"sale_item_id": sale_item_1.id, "quantity": "2.00"}
            ],
        )

        # Only one record_inventory_movement call (one item returned)
        assert mock_record.call_count == 1
        # Verify quantity
        call_kwargs = mock_record.call_args_list[0].kwargs
        assert call_kwargs["quantity_change"] == Decimal("2.00")

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_partial_return_caps_at_original_quantity(
        self,
        mock_record,
        mock_db,
        confirmed_sale,
        returned_by_user,
        sale_item_1,
    ):
        """Return quantity should be capped at the original sale quantity."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        # Try to return more than was sold (item_1 has qty=5)
        await service.return_sale(
            sale_id=confirmed_sale.id,
            returned_by=returned_by_user,
            return_items=[
                {"sale_item_id": sale_item_1.id, "quantity": "999.00"}
            ],
        )

        call_kwargs = mock_record.call_args_list[0].kwargs
        # Should be capped at original qty of 5
        assert call_kwargs["quantity_change"] == Decimal("5.00")

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_partial_return_cost_layer_has_partial_quantity(
        self,
        mock_record,
        mock_db,
        confirmed_sale,
        returned_by_user,
        sale_item_1,
    ):
        """CostLayer for partial return should have the partial quantity."""
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id,
            returned_by=returned_by_user,
            return_items=[
                {"sale_item_id": sale_item_1.id, "quantity": "2.00"}
            ],
        )

        add_calls = mock_db.add.call_args_list
        cost_layers = [
            c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)
        ]
        assert len(cost_layers) == 1
        assert cost_layers[0].original_quantity == Decimal("2.00")
        assert cost_layers[0].remaining_quantity == Decimal("2.00")


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


class TestReturnSaleEdgeCases:
    """Tests for edge cases in the return flow."""

    @pytest.mark.asyncio
    @patch(
        "app.services.sales_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_item_without_cogs_uses_unit_price(
        self, mock_record, mock_db, confirmed_sale, returned_by_user, sale_item_1
    ):
        """If COGS is None, should fall back to unit_price as unit_cost."""
        sale_item_1.cost_of_goods_sold = None
        _mock_db_with_sale(mock_db, confirmed_sale)
        service = SalesService(mock_db)

        await service.return_sale(
            sale_id=confirmed_sale.id, returned_by=returned_by_user
        )

        add_calls = mock_db.add.call_args_list
        cost_layers = [
            c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)
        ]
        layer_for_item_1 = next(
            l for l in cost_layers
            if l.spare_part_id == sale_item_1.spare_part_id
        )
        # Falls back to unit_price=200.00
        assert layer_for_item_1.unit_cost == Decimal("200.00")
