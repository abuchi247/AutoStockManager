"""Unit tests for the PurchaseService.

Tests validate:
1. PO creation in DRAFT status (Req 9.2)
2. PO approval (DRAFT → APPROVED) (Req 9.3)
3. PO approval rejection for non-DRAFT PO
4. PO approval rejection for PO with no items
5. Goods receipt (GRN) processing with ledger/cache/cost-layer integration (Req 9.4, 9.5)
6. GRN updates PO status to PARTIALLY_RECEIVED or RECEIVED (Req 9.6)
7. GRN creates supplier ledger debit entry
8. PO cancellation requires reason for non-DRAFT (Req 9.7)
9. PO cancellation without reason for DRAFT
10. Invalid GRN quantity exceeding remaining

Satisfies Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.models.cost_layer import CostLayer
from app.models.goods_receipt_note import GoodsReceiptNote
from app.models.grn_items import GRNItem
from app.models.inventory_movement_ledger import MovementType
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
)
from app.models.supplier_ledger import SupplierLedger, SupplierTransactionType
from app.services.purchase_service import (
    CancellationReasonRequiredError,
    InvalidGRNQuantityError,
    InvalidPOStatusError,
    POHasNoItemsError,
    PurchaseOrderNotFoundError,
    PurchaseService,
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
def user_id():
    """Generate a fixed user ID."""
    return uuid.uuid4()


@pytest.fixture
def supplier_id():
    """Generate a fixed supplier ID."""
    return uuid.uuid4()


@pytest.fixture
def location_id():
    """Generate a fixed location ID."""
    return uuid.uuid4()


@pytest.fixture
def spare_part_id():
    """Generate a fixed spare part ID."""
    return uuid.uuid4()


@pytest.fixture
def service(mock_db, user_id):
    """Create a PurchaseService instance with mocked db."""
    return PurchaseService(db=mock_db, user_id=user_id)


# =============================================================================
# Test: Create PO
# =============================================================================


class TestCreatePO:
    """Tests for PurchaseService.create_po."""

    @pytest.mark.asyncio
    async def test_creates_po_in_draft_status(self, service, mock_db, supplier_id, spare_part_id):
        """Req 9.2: PO initial state is draft."""
        items = [
            {
                "spare_part_id": spare_part_id,
                "quantity_ordered": Decimal("10"),
                "unit_cost": Decimal("50.00"),
            }
        ]

        po = await service.create_po(
            supplier_id=supplier_id,
            items=items,
            notes="Test PO",
        )

        assert po.status == PurchaseOrderStatus.DRAFT
        assert po.supplier_id == supplier_id
        assert po.notes == "Test PO"

    @pytest.mark.asyncio
    async def test_calculates_total_amount(self, service, mock_db, supplier_id, spare_part_id):
        """Req 9.8: Total = sum of (qty * unit_cost)."""
        items = [
            {
                "spare_part_id": spare_part_id,
                "quantity_ordered": Decimal("10"),
                "unit_cost": Decimal("50.00"),
            },
            {
                "spare_part_id": uuid.uuid4(),
                "quantity_ordered": Decimal("5"),
                "unit_cost": Decimal("100.00"),
            },
        ]

        po = await service.create_po(
            supplier_id=supplier_id,
            items=items,
        )

        # 10*50 + 5*100 = 500 + 500 = 1000
        assert po.total_amount == Decimal("1000.00")

    @pytest.mark.asyncio
    async def test_creates_po_items(self, service, mock_db, supplier_id, spare_part_id):
        """Verify PO items are added to the database."""
        items = [
            {
                "spare_part_id": spare_part_id,
                "quantity_ordered": Decimal("10"),
                "unit_cost": Decimal("50.00"),
            }
        ]

        await service.create_po(supplier_id=supplier_id, items=items)

        # Verify db.add was called for the PO and the item
        assert mock_db.add.call_count >= 2  # PO + at least 1 item


# =============================================================================
# Test: Approve PO
# =============================================================================


class TestApprovePO:
    """Tests for PurchaseService.approve_po."""

    @pytest.mark.asyncio
    async def test_approves_draft_po(self, service, mock_db, user_id):
        """Req 9.3: Manager/Admin approves PO (draft → approved)."""
        po_id = uuid.uuid4()
        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.DRAFT,
            total_amount=Decimal("500.00"),
        )
        # Add a mock item so the PO has items
        item = PurchaseOrderItem(
            id=uuid.uuid4(),
            purchase_order_id=po_id,
            spare_part_id=uuid.uuid4(),
            quantity_ordered=Decimal("10"),
            quantity_received=Decimal("0"),
            unit_cost=Decimal("50.00"),
        )
        po.items = [item]

        # Mock the _get_po_with_items to return our PO
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        approved_by = uuid.uuid4()
        result = await service.approve_po(po_id=po_id, approved_by=approved_by)

        assert result.status == PurchaseOrderStatus.APPROVED
        assert result.approved_by == approved_by
        assert result.approved_at is not None

    @pytest.mark.asyncio
    async def test_rejects_non_draft_po(self, service, mock_db):
        """Cannot approve a PO that's not in DRAFT status."""
        po_id = uuid.uuid4()
        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.APPROVED,
            total_amount=Decimal("500.00"),
        )
        po.items = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        with pytest.raises(InvalidPOStatusError) as exc_info:
            await service.approve_po(po_id=po_id, approved_by=uuid.uuid4())

        assert exc_info.value.current_status == PurchaseOrderStatus.APPROVED.value

    @pytest.mark.asyncio
    async def test_rejects_po_with_no_items(self, service, mock_db):
        """Cannot approve a PO with no items."""
        po_id = uuid.uuid4()
        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.DRAFT,
            total_amount=Decimal("0.00"),
        )
        po.items = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        with pytest.raises(POHasNoItemsError):
            await service.approve_po(po_id=po_id, approved_by=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_po_not_found(self, service, mock_db):
        """Raises PurchaseOrderNotFoundError for missing PO."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(PurchaseOrderNotFoundError):
            await service.approve_po(po_id=uuid.uuid4(), approved_by=uuid.uuid4())


# =============================================================================
# Test: Receive Goods (GRN)
# =============================================================================


class TestReceiveGoods:
    """Tests for PurchaseService.receive_goods."""

    @pytest.mark.asyncio
    async def test_creates_grn_for_approved_po(self, service, mock_db, location_id, user_id):
        """Req 9.4: Goods received creates GRN with received quantities."""
        po_id = uuid.uuid4()
        po_item_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()

        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.APPROVED,
            total_amount=Decimal("500.00"),
        )
        item = PurchaseOrderItem(
            id=po_item_id,
            purchase_order_id=po_id,
            spare_part_id=spare_part_id,
            quantity_ordered=Decimal("10"),
            quantity_received=Decimal("0"),
            unit_cost=Decimal("50.00"),
        )
        po.items = [item]

        # Mock the PO lookup
        mock_result_po = MagicMock()
        mock_result_po.scalar_one_or_none.return_value = po

        # Mock the stock cache lookup (for record_inventory_movement)
        mock_cache_result = MagicMock()
        mock_cache_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_result_po, mock_cache_result]

        grn_items = [
            {
                "po_item_id": po_item_id,
                "quantity_received": Decimal("5"),
            }
        ]

        grn = await service.receive_goods(
            po_id=po_id,
            location_id=location_id,
            received_by=user_id,
            items=grn_items,
            notes="First batch",
        )

        assert grn.purchase_order_id == po_id
        assert grn.location_id == location_id
        assert grn.received_by == user_id
        assert grn.notes == "First batch"

    @pytest.mark.asyncio
    async def test_updates_po_item_quantity_received(self, service, mock_db, location_id, user_id):
        """GRN updates PO item's quantity_received."""
        po_id = uuid.uuid4()
        po_item_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()

        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.APPROVED,
            total_amount=Decimal("500.00"),
        )
        item = PurchaseOrderItem(
            id=po_item_id,
            purchase_order_id=po_id,
            spare_part_id=spare_part_id,
            quantity_ordered=Decimal("10"),
            quantity_received=Decimal("0"),
            unit_cost=Decimal("50.00"),
        )
        po.items = [item]

        mock_result_po = MagicMock()
        mock_result_po.scalar_one_or_none.return_value = po
        mock_cache_result = MagicMock()
        mock_cache_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_result_po, mock_cache_result]

        grn_items = [{"po_item_id": po_item_id, "quantity_received": Decimal("5")}]

        await service.receive_goods(
            po_id=po_id,
            location_id=location_id,
            received_by=user_id,
            items=grn_items,
        )

        assert item.quantity_received == Decimal("5")

    @pytest.mark.asyncio
    async def test_partial_receipt_sets_partially_received(
        self, service, mock_db, location_id, user_id
    ):
        """Req 9.6: Partial receipt → PARTIALLY_RECEIVED."""
        po_id = uuid.uuid4()
        po_item_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()

        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.APPROVED,
            total_amount=Decimal("500.00"),
        )
        item = PurchaseOrderItem(
            id=po_item_id,
            purchase_order_id=po_id,
            spare_part_id=spare_part_id,
            quantity_ordered=Decimal("10"),
            quantity_received=Decimal("0"),
            unit_cost=Decimal("50.00"),
        )
        po.items = [item]

        mock_result_po = MagicMock()
        mock_result_po.scalar_one_or_none.return_value = po
        mock_cache_result = MagicMock()
        mock_cache_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_result_po, mock_cache_result]

        # Receive only 5 of 10 ordered
        grn_items = [{"po_item_id": po_item_id, "quantity_received": Decimal("5")}]

        await service.receive_goods(
            po_id=po_id,
            location_id=location_id,
            received_by=user_id,
            items=grn_items,
        )

        assert po.status == PurchaseOrderStatus.PARTIALLY_RECEIVED

    @pytest.mark.asyncio
    async def test_full_receipt_sets_received(self, service, mock_db, location_id, user_id):
        """Req 9.6: Full receipt → RECEIVED."""
        po_id = uuid.uuid4()
        po_item_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()

        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.APPROVED,
            total_amount=Decimal("500.00"),
        )
        item = PurchaseOrderItem(
            id=po_item_id,
            purchase_order_id=po_id,
            spare_part_id=spare_part_id,
            quantity_ordered=Decimal("10"),
            quantity_received=Decimal("0"),
            unit_cost=Decimal("50.00"),
        )
        po.items = [item]

        mock_result_po = MagicMock()
        mock_result_po.scalar_one_or_none.return_value = po
        mock_cache_result = MagicMock()
        mock_cache_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_result_po, mock_cache_result]

        # Receive all 10 of 10 ordered
        grn_items = [{"po_item_id": po_item_id, "quantity_received": Decimal("10")}]

        await service.receive_goods(
            po_id=po_id,
            location_id=location_id,
            received_by=user_id,
            items=grn_items,
        )

        assert po.status == PurchaseOrderStatus.RECEIVED

    @pytest.mark.asyncio
    async def test_rejects_non_receivable_status(self, service, mock_db, location_id, user_id):
        """Cannot receive goods for DRAFT or CANCELLED POs."""
        po_id = uuid.uuid4()
        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.DRAFT,
            total_amount=Decimal("0.00"),
        )
        po.items = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        with pytest.raises(InvalidPOStatusError):
            await service.receive_goods(
                po_id=po_id,
                location_id=location_id,
                received_by=user_id,
                items=[],
            )

    @pytest.mark.asyncio
    async def test_rejects_quantity_exceeding_remaining(
        self, service, mock_db, location_id, user_id
    ):
        """Cannot receive more than remaining ordered quantity."""
        po_id = uuid.uuid4()
        po_item_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()

        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.APPROVED,
            total_amount=Decimal("500.00"),
        )
        item = PurchaseOrderItem(
            id=po_item_id,
            purchase_order_id=po_id,
            spare_part_id=spare_part_id,
            quantity_ordered=Decimal("10"),
            quantity_received=Decimal("8"),  # Already received 8
            unit_cost=Decimal("50.00"),
        )
        po.items = [item]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        # Try to receive 5 but only 2 remaining
        grn_items = [{"po_item_id": po_item_id, "quantity_received": Decimal("5")}]

        with pytest.raises(InvalidGRNQuantityError) as exc_info:
            await service.receive_goods(
                po_id=po_id,
                location_id=location_id,
                received_by=user_id,
                items=grn_items,
            )

        assert exc_info.value.remaining == Decimal("2")

    @pytest.mark.asyncio
    async def test_creates_cost_layer(self, service, mock_db, location_id, user_id):
        """Req 9.5: GRN creates cost layer at receiving location."""
        po_id = uuid.uuid4()
        po_item_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()

        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.APPROVED,
            total_amount=Decimal("500.00"),
        )
        item = PurchaseOrderItem(
            id=po_item_id,
            purchase_order_id=po_id,
            spare_part_id=spare_part_id,
            quantity_ordered=Decimal("10"),
            quantity_received=Decimal("0"),
            unit_cost=Decimal("50.00"),
        )
        po.items = [item]

        mock_result_po = MagicMock()
        mock_result_po.scalar_one_or_none.return_value = po
        mock_cache_result = MagicMock()
        mock_cache_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_result_po, mock_cache_result]

        grn_items = [{"po_item_id": po_item_id, "quantity_received": Decimal("10")}]

        await service.receive_goods(
            po_id=po_id,
            location_id=location_id,
            received_by=user_id,
            items=grn_items,
        )

        # Verify a CostLayer was added via db.add
        added_objects = [call.args[0] for call in mock_db.add.call_args_list]
        cost_layers = [obj for obj in added_objects if isinstance(obj, CostLayer)]

        assert len(cost_layers) == 1
        cl = cost_layers[0]
        assert cl.spare_part_id == spare_part_id
        assert cl.location_id == location_id
        assert cl.unit_cost == Decimal("50.00")
        assert cl.original_quantity == Decimal("10")
        assert cl.remaining_quantity == Decimal("10")
        assert cl.source_type == "purchase"

    @pytest.mark.asyncio
    async def test_creates_supplier_ledger_entry(self, service, mock_db, location_id, user_id):
        """GRN creates a purchase debit in SupplierLedger."""
        po_id = uuid.uuid4()
        po_item_id = uuid.uuid4()
        spare_part_id = uuid.uuid4()
        supplier_id = uuid.uuid4()

        po = PurchaseOrder(
            id=po_id,
            supplier_id=supplier_id,
            status=PurchaseOrderStatus.APPROVED,
            total_amount=Decimal("500.00"),
        )
        item = PurchaseOrderItem(
            id=po_item_id,
            purchase_order_id=po_id,
            spare_part_id=spare_part_id,
            quantity_ordered=Decimal("10"),
            quantity_received=Decimal("0"),
            unit_cost=Decimal("50.00"),
        )
        po.items = [item]

        mock_result_po = MagicMock()
        mock_result_po.scalar_one_or_none.return_value = po
        mock_cache_result = MagicMock()
        mock_cache_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [mock_result_po, mock_cache_result]

        grn_items = [{"po_item_id": po_item_id, "quantity_received": Decimal("10")}]

        await service.receive_goods(
            po_id=po_id,
            location_id=location_id,
            received_by=user_id,
            items=grn_items,
        )

        # Verify a SupplierLedger entry was added
        added_objects = [call.args[0] for call in mock_db.add.call_args_list]
        ledger_entries = [obj for obj in added_objects if isinstance(obj, SupplierLedger)]

        assert len(ledger_entries) == 1
        entry = ledger_entries[0]
        assert entry.supplier_id == supplier_id
        assert entry.transaction_type == SupplierTransactionType.PURCHASE.value
        assert entry.amount == Decimal("500.00")  # 10 * 50


# =============================================================================
# Test: Cancel PO
# =============================================================================


class TestCancelPO:
    """Tests for PurchaseService.cancel_po."""

    @pytest.mark.asyncio
    async def test_cancels_draft_without_reason(self, service, mock_db):
        """DRAFT POs can be cancelled without a reason."""
        po_id = uuid.uuid4()
        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.DRAFT,
            total_amount=Decimal("0.00"),
        )
        po.items = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        result = await service.cancel_po(
            po_id=po_id,
            cancelled_by=uuid.uuid4(),
        )

        assert result.status == PurchaseOrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancels_approved_with_reason(self, service, mock_db):
        """Req 9.7: Non-DRAFT POs require a cancellation reason."""
        po_id = uuid.uuid4()
        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.APPROVED,
            total_amount=Decimal("500.00"),
        )
        po.items = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        result = await service.cancel_po(
            po_id=po_id,
            cancelled_by=uuid.uuid4(),
            reason="Supplier cannot fulfill order",
        )

        assert result.status == PurchaseOrderStatus.CANCELLED
        assert "Supplier cannot fulfill order" in result.notes

    @pytest.mark.asyncio
    async def test_requires_reason_for_non_draft(self, service, mock_db):
        """Req 9.7: Cancelling ordered/partially_received requires reason."""
        po_id = uuid.uuid4()
        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.ORDERED,
            total_amount=Decimal("500.00"),
        )
        po.items = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        with pytest.raises(CancellationReasonRequiredError):
            await service.cancel_po(
                po_id=po_id,
                cancelled_by=uuid.uuid4(),
                reason=None,
            )

    @pytest.mark.asyncio
    async def test_cannot_cancel_received_po(self, service, mock_db):
        """Cannot cancel a fully received PO."""
        po_id = uuid.uuid4()
        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.RECEIVED,
            total_amount=Decimal("500.00"),
        )
        po.items = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        with pytest.raises(InvalidPOStatusError):
            await service.cancel_po(
                po_id=po_id,
                cancelled_by=uuid.uuid4(),
                reason="Some reason",
            )

    @pytest.mark.asyncio
    async def test_cannot_cancel_already_cancelled(self, service, mock_db):
        """Cannot cancel a PO that's already cancelled."""
        po_id = uuid.uuid4()
        po = PurchaseOrder(
            id=po_id,
            supplier_id=uuid.uuid4(),
            status=PurchaseOrderStatus.CANCELLED,
            total_amount=Decimal("0.00"),
        )
        po.items = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = po
        mock_db.execute.return_value = mock_result

        with pytest.raises(InvalidPOStatusError):
            await service.cancel_po(
                po_id=po_id,
                cancelled_by=uuid.uuid4(),
                reason="Duplicate",
            )
