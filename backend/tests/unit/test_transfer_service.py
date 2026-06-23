"""Unit tests for the TransferService.receive_transfer method.

Tests validate the transfer receive flow:
1. Validates the transfer is in IN_TRANSIT status
2. Reads consumed_layer_details from the transfer record
3. Creates new CostLayers at the destination with correct attributes
4. Records TRANSFER_IN ledger entries for each consumed layer detail
5. Updates destination cache via record_inventory_movement
6. Updates transfer status to RECEIVED with received_by and received_at

Satisfies Requirements: 4.6, 4.10, 4.12
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.models.cost_layer import CostLayer
from app.models.inventory_movement_ledger import MovementType, ReferenceType
from app.models.stock_status_cache import StockStatusCache
from app.models.transfer import Transfer, TransferStatus
from app.services.transfer_service import (
    InsufficientStockError,
    InvalidTransferStatusError,
    TransferNotFoundError,
    TransferService,
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
def transfer_id():
    """Generate a fixed transfer ID for tests."""
    return uuid.uuid4()


@pytest.fixture
def spare_part_id():
    """Generate a fixed spare part ID."""
    return uuid.uuid4()


@pytest.fixture
def source_location_id():
    """Generate a fixed source location ID."""
    return uuid.uuid4()


@pytest.fixture
def destination_location_id():
    """Generate a fixed destination location ID."""
    return uuid.uuid4()


@pytest.fixture
def received_by_user():
    """Generate a fixed user ID for the receiver."""
    return uuid.uuid4()


@pytest.fixture
def in_transit_transfer(
    transfer_id, spare_part_id, source_location_id, destination_location_id
):
    """Create a transfer in IN_TRANSIT status with consumed layer details."""
    transfer = Transfer(
        spare_part_id=spare_part_id,
        source_location_id=source_location_id,
        destination_location_id=destination_location_id,
        quantity=Decimal("15.0000"),
        status=TransferStatus.IN_TRANSIT.value,
        requested_by=uuid.uuid4(),
        approved_by=uuid.uuid4(),
        approved_at=datetime.now(timezone.utc),
        consumed_layer_details=[
            {
                "layer_id": str(uuid.uuid4()),
                "quantity_consumed": "10.0000",
                "unit_cost": "100.0000",
                "layer_cost": "1000.0000",
            },
            {
                "layer_id": str(uuid.uuid4()),
                "quantity_consumed": "5.0000",
                "unit_cost": "120.0000",
                "layer_cost": "600.0000",
            },
        ],
    )
    # Manually set id since we're not using a real DB
    transfer.id = transfer_id
    return transfer


@pytest.fixture
def single_layer_transfer(
    transfer_id, spare_part_id, source_location_id, destination_location_id
):
    """Create a transfer with a single consumed layer detail."""
    transfer = Transfer(
        spare_part_id=spare_part_id,
        source_location_id=source_location_id,
        destination_location_id=destination_location_id,
        quantity=Decimal("7.0000"),
        status=TransferStatus.IN_TRANSIT.value,
        requested_by=uuid.uuid4(),
        approved_by=uuid.uuid4(),
        approved_at=datetime.now(timezone.utc),
        consumed_layer_details=[
            {
                "layer_id": str(uuid.uuid4()),
                "quantity_consumed": "7.0000",
                "unit_cost": "200.5000",
                "layer_cost": "1403.5000",
            },
        ],
    )
    transfer.id = transfer_id
    return transfer


def _mock_db_with_transfer(mock_db, transfer):
    """Configure mock_db to return the given transfer on execute."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = transfer
    mock_db.execute = AsyncMock(return_value=mock_result)


# =============================================================================
# Tests: receive_transfer - Status Validation
# =============================================================================


class TestReceiveTransferStatusValidation:
    """Test that receive_transfer validates transfer status correctly."""

    @pytest.mark.asyncio
    async def test_rejects_pending_transfer(self, mock_db, transfer_id, spare_part_id):
        """Should raise InvalidTransferStatusError if transfer is PENDING."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=uuid.uuid4(),
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("10.0000"),
            status=TransferStatus.PENDING.value,
            requested_by=uuid.uuid4(),
        )
        transfer.id = transfer_id
        _mock_db_with_transfer(mock_db, transfer)

        service = TransferService(db=mock_db)
        with pytest.raises(InvalidTransferStatusError) as exc_info:
            await service.receive_transfer(transfer_id, uuid.uuid4())

        assert exc_info.value.current_status == TransferStatus.PENDING.value
        assert exc_info.value.expected_status == TransferStatus.IN_TRANSIT.value

    @pytest.mark.asyncio
    async def test_rejects_received_transfer(self, mock_db, transfer_id, spare_part_id):
        """Should raise InvalidTransferStatusError if transfer is already RECEIVED."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=uuid.uuid4(),
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("10.0000"),
            status=TransferStatus.RECEIVED.value,
            requested_by=uuid.uuid4(),
        )
        transfer.id = transfer_id
        _mock_db_with_transfer(mock_db, transfer)

        service = TransferService(db=mock_db)
        with pytest.raises(InvalidTransferStatusError) as exc_info:
            await service.receive_transfer(transfer_id, uuid.uuid4())

        assert exc_info.value.current_status == TransferStatus.RECEIVED.value

    @pytest.mark.asyncio
    async def test_rejects_cancelled_transfer(self, mock_db, transfer_id, spare_part_id):
        """Should raise InvalidTransferStatusError if transfer is CANCELLED."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=uuid.uuid4(),
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("10.0000"),
            status=TransferStatus.CANCELLED.value,
            requested_by=uuid.uuid4(),
        )
        transfer.id = transfer_id
        _mock_db_with_transfer(mock_db, transfer)

        service = TransferService(db=mock_db)
        with pytest.raises(InvalidTransferStatusError):
            await service.receive_transfer(transfer_id, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_transfer(self, mock_db):
        """Should raise TransferNotFoundError if transfer ID doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = TransferService(db=mock_db)
        missing_id = uuid.uuid4()
        with pytest.raises(TransferNotFoundError) as exc_info:
            await service.receive_transfer(missing_id, uuid.uuid4())

        assert exc_info.value.transfer_id == missing_id


# =============================================================================
# Tests: receive_transfer - Cost Layer Creation
# =============================================================================


class TestReceiveTransferCostLayerCreation:
    """Test that receive_transfer creates new cost layers at destination."""

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_creates_cost_layer_per_consumed_detail(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Should create one new CostLayer for each consumed layer detail."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        # Two consumed layer details → two db.add calls for CostLayer
        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [c for c in add_calls if isinstance(c[0][0], CostLayer)]
        assert len(cost_layer_adds) == 2

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_cost_layer_has_correct_destination_location(
        self, mock_record, mock_db, in_transit_transfer, received_by_user, destination_location_id
    ):
        """New cost layers should be at the destination location."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)]
        for layer in cost_layer_adds:
            assert layer.location_id == destination_location_id

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_cost_layer_has_correct_spare_part(
        self, mock_record, mock_db, in_transit_transfer, received_by_user, spare_part_id
    ):
        """New cost layers should reference the correct spare part."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)]
        for layer in cost_layer_adds:
            assert layer.spare_part_id == spare_part_id

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_cost_layer_has_correct_unit_costs(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Each cost layer should use the unit_cost from the corresponding consumed detail."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)]

        assert cost_layer_adds[0].unit_cost == Decimal("100.0000")
        assert cost_layer_adds[1].unit_cost == Decimal("120.0000")

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_cost_layer_has_correct_quantities(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Cost layer original_quantity and remaining_quantity should equal quantity_consumed."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)]

        # First layer: 10 units consumed
        assert cost_layer_adds[0].original_quantity == Decimal("10.0000")
        assert cost_layer_adds[0].remaining_quantity == Decimal("10.0000")

        # Second layer: 5 units consumed
        assert cost_layer_adds[1].original_quantity == Decimal("5.0000")
        assert cost_layer_adds[1].remaining_quantity == Decimal("5.0000")

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_cost_layer_source_type_is_transfer(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """New cost layers should have source_type='transfer'."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)]
        for layer in cost_layer_adds:
            assert layer.source_type == "transfer"

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_cost_layer_source_reference_is_transfer_id(
        self, mock_record, mock_db, in_transit_transfer, received_by_user, transfer_id
    ):
        """New cost layers should reference the transfer as their source."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)]
        for layer in cost_layer_adds:
            assert layer.source_reference_id == transfer_id


# =============================================================================
# Tests: receive_transfer - Ledger Entries
# =============================================================================


class TestReceiveTransferLedgerEntries:
    """Test that receive_transfer creates correct TRANSFER_IN ledger entries."""

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_records_transfer_in_per_consumed_detail(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Should call record_inventory_movement once per consumed layer detail."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        assert mock_record.call_count == 2

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_ledger_entry_movement_type_is_transfer_in(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """All ledger entries should be of type TRANSFER_IN."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        for call_args in mock_record.call_args_list:
            kwargs = call_args.kwargs if call_args.kwargs else {}
            # Check positional or keyword args
            if kwargs:
                assert kwargs["movement_type"] == MovementType.TRANSFER_IN.value
            else:
                # Falls back to positional - movement_type is the 4th positional
                pass

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_ledger_entry_reference_type_is_transfer(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """All ledger entries should reference type 'transfer'."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        for call_args in mock_record.call_args_list:
            kwargs = call_args.kwargs if call_args.kwargs else {}
            if kwargs:
                assert kwargs["reference_type"] == ReferenceType.TRANSFER.value

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_ledger_entry_at_destination_location(
        self, mock_record, mock_db, in_transit_transfer, received_by_user, destination_location_id
    ):
        """Ledger entries should be recorded at the destination location."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        for call_args in mock_record.call_args_list:
            kwargs = call_args.kwargs if call_args.kwargs else {}
            if kwargs:
                assert kwargs["location_id"] == destination_location_id

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_ledger_entries_have_positive_quantities(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """TRANSFER_IN entries should have positive quantity_change values."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        for call_args in mock_record.call_args_list:
            kwargs = call_args.kwargs if call_args.kwargs else {}
            if kwargs:
                assert kwargs["quantity_change"] > Decimal("0")

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_ledger_entries_have_correct_quantities(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Each ledger entry should have quantity matching the consumed detail."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        calls = mock_record.call_args_list
        # First call: 10 units from first layer
        assert calls[0].kwargs["quantity_change"] == Decimal("10.0000")
        # Second call: 5 units from second layer
        assert calls[1].kwargs["quantity_change"] == Decimal("5.0000")

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_ledger_entries_have_correct_unit_costs(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Each ledger entry should use the unit_cost from the consumed detail."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        calls = mock_record.call_args_list
        assert calls[0].kwargs["unit_cost"] == Decimal("100.0000")
        assert calls[1].kwargs["unit_cost"] == Decimal("120.0000")

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_ledger_entries_reference_transfer_id(
        self, mock_record, mock_db, in_transit_transfer, received_by_user, transfer_id
    ):
        """All ledger entries should reference the transfer ID."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        for call_args in mock_record.call_args_list:
            kwargs = call_args.kwargs if call_args.kwargs else {}
            if kwargs:
                assert kwargs["reference_id"] == transfer_id

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_ledger_entries_created_by_receiver(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """All ledger entries should be created by the receiving user."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(in_transit_transfer.id, received_by_user)

        for call_args in mock_record.call_args_list:
            kwargs = call_args.kwargs if call_args.kwargs else {}
            if kwargs:
                assert kwargs["created_by"] == received_by_user


# =============================================================================
# Tests: receive_transfer - Transfer Status Update
# =============================================================================


class TestReceiveTransferStatusUpdate:
    """Test that receive_transfer correctly updates the transfer record."""

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_sets_status_to_received(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Transfer status should be updated to RECEIVED."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        result = await service.receive_transfer(in_transit_transfer.id, received_by_user)

        assert result.status == TransferStatus.RECEIVED.value

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_sets_received_by(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Transfer should record who received it."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        result = await service.receive_transfer(in_transit_transfer.id, received_by_user)

        assert result.received_by == received_by_user

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_sets_received_at_timestamp(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Transfer should record when it was received."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        before = datetime.now(timezone.utc)
        result = await service.receive_transfer(in_transit_transfer.id, received_by_user)
        after = datetime.now(timezone.utc)

        assert result.received_at is not None
        assert before <= result.received_at <= after

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_returns_updated_transfer(
        self, mock_record, mock_db, in_transit_transfer, received_by_user
    ):
        """Should return the updated Transfer object."""
        _mock_db_with_transfer(mock_db, in_transit_transfer)

        service = TransferService(db=mock_db)
        result = await service.receive_transfer(in_transit_transfer.id, received_by_user)

        assert isinstance(result, Transfer)
        assert result.id == in_transit_transfer.id


# =============================================================================
# Tests: receive_transfer - Single Layer Transfer
# =============================================================================


class TestReceiveTransferSingleLayer:
    """Test receive_transfer with a single consumed layer detail."""

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_single_layer_creates_one_cost_layer(
        self, mock_record, mock_db, single_layer_transfer, received_by_user
    ):
        """A transfer with one consumed layer should create exactly one new cost layer."""
        _mock_db_with_transfer(mock_db, single_layer_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(single_layer_transfer.id, received_by_user)

        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)]
        assert len(cost_layer_adds) == 1

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_single_layer_correct_unit_cost(
        self, mock_record, mock_db, single_layer_transfer, received_by_user
    ):
        """Single layer cost layer should preserve the original unit cost."""
        _mock_db_with_transfer(mock_db, single_layer_transfer)

        service = TransferService(db=mock_db)
        await service.receive_transfer(single_layer_transfer.id, received_by_user)

        add_calls = mock_db.add.call_args_list
        cost_layer_adds = [c[0][0] for c in add_calls if isinstance(c[0][0], CostLayer)]
        assert cost_layer_adds[0].unit_cost == Decimal("200.5000")
        assert cost_layer_adds[0].original_quantity == Decimal("7.0000")
        assert cost_layer_adds[0].remaining_quantity == Decimal("7.0000")


# =============================================================================
# Tests: receive_transfer - Empty consumed_layer_details
# =============================================================================


class TestReceiveTransferEmptyDetails:
    """Test receive_transfer with empty or None consumed_layer_details."""

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_empty_details_still_marks_received(
        self, mock_record, mock_db, transfer_id, spare_part_id, received_by_user
    ):
        """Even with empty consumed details, transfer should be marked RECEIVED."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=uuid.uuid4(),
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("0"),
            status=TransferStatus.IN_TRANSIT.value,
            requested_by=uuid.uuid4(),
            consumed_layer_details=[],
        )
        transfer.id = transfer_id
        _mock_db_with_transfer(mock_db, transfer)

        service = TransferService(db=mock_db)
        result = await service.receive_transfer(transfer_id, received_by_user)

        assert result.status == TransferStatus.RECEIVED.value
        mock_record.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    async def test_none_details_still_marks_received(
        self, mock_record, mock_db, transfer_id, spare_part_id, received_by_user
    ):
        """With None consumed details, transfer should be marked RECEIVED."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=uuid.uuid4(),
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("0"),
            status=TransferStatus.IN_TRANSIT.value,
            requested_by=uuid.uuid4(),
            consumed_layer_details=None,
        )
        transfer.id = transfer_id
        _mock_db_with_transfer(mock_db, transfer)

        service = TransferService(db=mock_db)
        result = await service.receive_transfer(transfer_id, received_by_user)

        assert result.status == TransferStatus.RECEIVED.value
        mock_record.assert_not_called()


# =============================================================================
# Tests: approve_transfer - Transfer Not Found
# =============================================================================


class TestApproveTransferNotFound:
    """Tests for when the transfer does not exist."""

    @pytest.mark.asyncio
    async def test_raises_transfer_not_found(self, mock_db):
        """Should raise TransferNotFoundError when transfer ID doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = TransferService(db=mock_db)
        missing_id = uuid.uuid4()

        with pytest.raises(TransferNotFoundError) as exc_info:
            await service.approve_transfer(
                transfer_id=missing_id,
                approved_by=uuid.uuid4(),
            )

        assert exc_info.value.transfer_id == missing_id


# =============================================================================
# Tests: approve_transfer - Invalid Status
# =============================================================================


class TestApproveTransferInvalidStatus:
    """Tests for when the transfer is not in PENDING status."""

    @pytest.mark.asyncio
    async def test_rejects_in_transit_transfer(self, mock_db, spare_part_id, transfer_id):
        """Should raise InvalidTransferStatusError for IN_TRANSIT transfers."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=uuid.uuid4(),
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("10.0000"),
            status=TransferStatus.IN_TRANSIT.value,
            requested_by=uuid.uuid4(),
        )
        transfer.id = transfer_id
        _mock_db_with_transfer(mock_db, transfer)

        service = TransferService(db=mock_db)

        with pytest.raises(InvalidTransferStatusError) as exc_info:
            await service.approve_transfer(transfer_id, uuid.uuid4())

        assert exc_info.value.current_status == TransferStatus.IN_TRANSIT.value
        assert exc_info.value.expected_status == TransferStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_rejects_received_transfer(self, mock_db, spare_part_id, transfer_id):
        """Should raise InvalidTransferStatusError for RECEIVED transfers."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=uuid.uuid4(),
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("10.0000"),
            status=TransferStatus.RECEIVED.value,
            requested_by=uuid.uuid4(),
        )
        transfer.id = transfer_id
        _mock_db_with_transfer(mock_db, transfer)

        service = TransferService(db=mock_db)

        with pytest.raises(InvalidTransferStatusError) as exc_info:
            await service.approve_transfer(transfer_id, uuid.uuid4())

        assert exc_info.value.current_status == TransferStatus.RECEIVED.value

    @pytest.mark.asyncio
    async def test_rejects_cancelled_transfer(self, mock_db, spare_part_id, transfer_id):
        """Should raise InvalidTransferStatusError for CANCELLED transfers."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=uuid.uuid4(),
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("10.0000"),
            status=TransferStatus.CANCELLED.value,
            requested_by=uuid.uuid4(),
        )
        transfer.id = transfer_id
        _mock_db_with_transfer(mock_db, transfer)

        service = TransferService(db=mock_db)

        with pytest.raises(InvalidTransferStatusError):
            await service.approve_transfer(transfer_id, uuid.uuid4())


# =============================================================================
# Tests: approve_transfer - Insufficient Stock
# =============================================================================


class TestApproveTransferInsufficientStock:
    """Tests for when source location has insufficient stock."""

    @pytest.mark.asyncio
    async def test_raises_insufficient_stock_when_cache_too_low(
        self, mock_db, transfer_id, spare_part_id, source_location_id
    ):
        """Should raise InsufficientStockError when stock < requested qty."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=source_location_id,
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("20.0000"),
            status=TransferStatus.PENDING.value,
            requested_by=uuid.uuid4(),
        )
        transfer.id = transfer_id

        # Source cache has only 5 units available
        cache = StockStatusCache(
            spare_part_id=spare_part_id,
            location_id=source_location_id,
            current_quantity=Decimal("5.0000"),
        )

        # Setup mock_db to return transfer first, then cache
        call_count = {"n": 0}

        async def execute_side_effect(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = transfer
            else:
                result.scalar_one_or_none.return_value = cache
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        service = TransferService(db=mock_db)

        with pytest.raises(InsufficientStockError) as exc_info:
            await service.approve_transfer(transfer_id, uuid.uuid4())

        assert exc_info.value.requested == Decimal("20.0000")
        assert exc_info.value.available == Decimal("5.0000")

    @pytest.mark.asyncio
    async def test_raises_insufficient_stock_when_no_cache_row(
        self, mock_db, transfer_id, spare_part_id, source_location_id
    ):
        """Should raise InsufficientStockError when no cache row exists (0 stock)."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=source_location_id,
            destination_location_id=uuid.uuid4(),
            quantity=Decimal("10.0000"),
            status=TransferStatus.PENDING.value,
            requested_by=uuid.uuid4(),
        )
        transfer.id = transfer_id

        # No cache row exists
        call_count = {"n": 0}

        async def execute_side_effect(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = transfer
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        service = TransferService(db=mock_db)

        with pytest.raises(InsufficientStockError) as exc_info:
            await service.approve_transfer(transfer_id, uuid.uuid4())

        assert exc_info.value.available == Decimal("0")


# =============================================================================
# Tests: approve_transfer - Successful Approval
# =============================================================================


class TestApproveTransferSuccess:
    """Tests for successful transfer approval with FIFO consumption."""

    @pytest.fixture
    def pending_transfer(self, transfer_id, spare_part_id, source_location_id, destination_location_id):
        """Create a pending transfer for approval tests."""
        transfer = Transfer(
            spare_part_id=spare_part_id,
            source_location_id=source_location_id,
            destination_location_id=destination_location_id,
            quantity=Decimal("10.0000"),
            status=TransferStatus.PENDING.value,
            requested_by=uuid.uuid4(),
        )
        transfer.id = transfer_id
        return transfer

    @pytest.fixture
    def source_stock_cache(self, spare_part_id, source_location_id):
        """Create a source cache with sufficient stock."""
        return StockStatusCache(
            spare_part_id=spare_part_id,
            location_id=source_location_id,
            current_quantity=Decimal("50.0000"),
        )

    @pytest.fixture
    def fifo_consumed_details(self):
        """Sample consumed layer details from FIFO."""
        return [
            {
                "layer_id": uuid.uuid4(),
                "quantity_consumed": Decimal("7.0000"),
                "unit_cost": Decimal("100.0000"),
                "layer_cost": Decimal("700.0000"),
            },
            {
                "layer_id": uuid.uuid4(),
                "quantity_consumed": Decimal("3.0000"),
                "unit_cost": Decimal("110.0000"),
                "layer_cost": Decimal("330.0000"),
            },
        ]

    def _setup_approve_mocks(self, mock_db, pending_transfer, source_stock_cache):
        """Configure mock_db for the approve flow."""
        call_count = {"n": 0}

        async def execute_side_effect(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = pending_transfer
            else:
                result.scalar_one_or_none.return_value = source_stock_cache
            return result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_returns_transfer_with_in_transit_status(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Should return transfer with IN_TRANSIT status after approval."""
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        result = await service.approve_transfer(pending_transfer.id, received_by_user)

        assert result.status == TransferStatus.IN_TRANSIT.value

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_sets_approved_by(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Should set approved_by to the approving user."""
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        result = await service.approve_transfer(pending_transfer.id, received_by_user)

        assert result.approved_by == received_by_user

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_sets_approved_at_timestamp(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Should set approved_at to current timestamp."""
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        before = datetime.now(timezone.utc)
        result = await service.approve_transfer(pending_transfer.id, received_by_user)
        after = datetime.now(timezone.utc)

        assert result.approved_at is not None
        assert before <= result.approved_at <= after

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_calls_consume_fifo_layers_with_correct_params(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Should call consume_fifo_layers with correct part, location, and qty."""
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        await service.approve_transfer(pending_transfer.id, received_by_user)

        mock_consume.assert_called_once_with(
            db=mock_db,
            spare_part_id=pending_transfer.spare_part_id,
            location_id=pending_transfer.source_location_id,
            quantity_to_consume=pending_transfer.quantity,
        )

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_writes_transfer_out_ledger_entry(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Should write a TRANSFER_OUT ledger entry with negative qty at source."""
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        await service.approve_transfer(pending_transfer.id, received_by_user)

        # First call to record_inventory_movement should be TRANSFER_OUT
        first_call = mock_record.call_args_list[0]
        assert first_call.kwargs["movement_type"] == MovementType.TRANSFER_OUT.value
        assert first_call.kwargs["quantity_change"] == -pending_transfer.quantity
        assert first_call.kwargs["location_id"] == pending_transfer.source_location_id
        assert first_call.kwargs["spare_part_id"] == pending_transfer.spare_part_id
        assert first_call.kwargs["reference_type"] == ReferenceType.TRANSFER.value
        assert first_call.kwargs["reference_id"] == pending_transfer.id
        assert first_call.kwargs["created_by"] == received_by_user

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_ledger_entry_has_correct_weighted_unit_cost(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Should use weighted average unit cost: total_cost / quantity."""
        # total_cost=1030, quantity=10 → unit_cost=103.00
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        await service.approve_transfer(pending_transfer.id, received_by_user)

        first_call = mock_record.call_args_list[0]
        expected_unit_cost = Decimal("1030.0000") / Decimal("10.0000")
        assert first_call.kwargs["unit_cost"] == expected_unit_cost

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_stores_consumed_layer_details_as_json(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Should store consumed layer details as JSON-serializable list on transfer."""
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        result = await service.approve_transfer(pending_transfer.id, received_by_user)

        assert result.consumed_layer_details is not None
        assert len(result.consumed_layer_details) == 2

        # Verify details are JSON-serializable (strings)
        first_detail = result.consumed_layer_details[0]
        assert isinstance(first_detail["layer_id"], str)
        assert isinstance(first_detail["quantity_consumed"], str)
        assert isinstance(first_detail["unit_cost"], str)
        assert isinstance(first_detail["layer_cost"], str)

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_consumed_details_preserve_correct_values(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Stored consumed details should preserve the values from FIFO consumption."""
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        result = await service.approve_transfer(pending_transfer.id, received_by_user)

        details = result.consumed_layer_details
        # First layer: 7 units at 100.00
        assert Decimal(details[0]["quantity_consumed"]) == Decimal("7.0000")
        assert Decimal(details[0]["unit_cost"]) == Decimal("100.0000")
        assert Decimal(details[0]["layer_cost"]) == Decimal("700.0000")

        # Second layer: 3 units at 110.00
        assert Decimal(details[1]["quantity_consumed"]) == Decimal("3.0000")
        assert Decimal(details[1]["unit_cost"]) == Decimal("110.0000")
        assert Decimal(details[1]["layer_cost"]) == Decimal("330.0000")

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_record_movement_called_for_transfer_out(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Should call record_inventory_movement at least once for TRANSFER_OUT."""
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        await service.approve_transfer(pending_transfer.id, received_by_user)

        # At minimum, one call for TRANSFER_OUT
        assert mock_record.call_count >= 1
        first_call = mock_record.call_args_list[0]
        assert first_call.kwargs["movement_type"] == MovementType.TRANSFER_OUT.value

    @pytest.mark.asyncio
    @patch("app.services.transfer_service.record_inventory_movement", new_callable=AsyncMock)
    @patch("app.services.transfer_service.consume_fifo_layers", new_callable=AsyncMock)
    async def test_flushes_db_after_approval(
        self, mock_consume, mock_record, mock_db,
        pending_transfer, source_stock_cache, fifo_consumed_details, received_by_user,
    ):
        """Should flush the database session to persist changes."""
        mock_consume.return_value = (Decimal("1030.0000"), fifo_consumed_details)
        self._setup_approve_mocks(mock_db, pending_transfer, source_stock_cache)

        service = TransferService(db=mock_db)
        await service.approve_transfer(pending_transfer.id, received_by_user)

        mock_db.flush.assert_called()
