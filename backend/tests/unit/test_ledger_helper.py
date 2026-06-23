"""Unit tests for the atomic ledger-write + cache-update helper.

Tests validate that the record_inventory_movement function:
1. Creates an InventoryMovementLedger entry with correct fields
2. Creates/updates a StockStatusCache row atomically
3. Handles both existing and new cache rows (upsert pattern)
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.inventory_movement_ledger import (
    InventoryMovementLedger,
    MovementType,
    ReferenceType,
)
from app.models.stock_status_cache import StockStatusCache
from app.utils.ledger import record_inventory_movement


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def sample_params():
    """Standard parameters for record_inventory_movement calls."""
    return {
        "spare_part_id": uuid.uuid4(),
        "location_id": uuid.uuid4(),
        "quantity_change": Decimal("10.0000"),
        "movement_type": MovementType.PURCHASE,
        "reference_type": ReferenceType.GRN,
        "reference_id": uuid.uuid4(),
        "unit_cost": Decimal("150.5000"),
        "created_by": uuid.uuid4(),
    }


class TestRecordInventoryMovementNewCache:
    """Test behavior when no cache row exists (INSERT path)."""

    @pytest.mark.asyncio
    async def test_creates_ledger_entry(self, mock_db, sample_params):
        """Should add an InventoryMovementLedger instance to the session."""
        # Mock: no existing cache row
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await record_inventory_movement(db=mock_db, **sample_params)

        # Verify a ledger entry was added
        assert isinstance(result, InventoryMovementLedger)
        assert result.spare_part_id == sample_params["spare_part_id"]
        assert result.location_id == sample_params["location_id"]
        assert result.quantity_change == sample_params["quantity_change"]
        assert result.movement_type == sample_params["movement_type"]
        assert result.reference_type == sample_params["reference_type"]
        assert result.reference_id == sample_params["reference_id"]
        assert result.unit_cost == sample_params["unit_cost"]
        assert result.created_by == sample_params["created_by"]

    @pytest.mark.asyncio
    async def test_creates_new_cache_row_when_none_exists(self, mock_db, sample_params):
        """Should create a new StockStatusCache row when none exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        await record_inventory_movement(db=mock_db, **sample_params)

        # db.add should be called twice: once for ledger, once for cache
        assert mock_db.add.call_count == 2
        # Second call should be the cache row
        cache_arg = mock_db.add.call_args_list[1][0][0]
        assert isinstance(cache_arg, StockStatusCache)
        assert cache_arg.spare_part_id == sample_params["spare_part_id"]
        assert cache_arg.location_id == sample_params["location_id"]
        assert cache_arg.current_quantity == sample_params["quantity_change"]

    @pytest.mark.asyncio
    async def test_flushes_twice(self, mock_db, sample_params):
        """Should flush after ledger write and after cache update."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        await record_inventory_movement(db=mock_db, **sample_params)

        assert mock_db.flush.call_count == 2


class TestRecordInventoryMovementExistingCache:
    """Test behavior when a cache row already exists (UPDATE path)."""

    @pytest.mark.asyncio
    async def test_updates_existing_cache_row(self, mock_db, sample_params):
        """Should update the existing cache row's current_quantity."""
        existing_cache = StockStatusCache(
            spare_part_id=sample_params["spare_part_id"],
            location_id=sample_params["location_id"],
            current_quantity=Decimal("50.0000"),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_cache
        mock_db.execute = AsyncMock(return_value=mock_result)

        await record_inventory_movement(db=mock_db, **sample_params)

        # Cache should be updated: 50 + 10 = 60
        assert existing_cache.current_quantity == Decimal("60.0000")

    @pytest.mark.asyncio
    async def test_updates_cache_with_negative_quantity(self, mock_db, sample_params):
        """Should correctly reduce cache quantity for outflows (negative change)."""
        sample_params["quantity_change"] = Decimal("-5.0000")
        sample_params["movement_type"] = MovementType.SALE

        existing_cache = StockStatusCache(
            spare_part_id=sample_params["spare_part_id"],
            location_id=sample_params["location_id"],
            current_quantity=Decimal("50.0000"),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_cache
        mock_db.execute = AsyncMock(return_value=mock_result)

        await record_inventory_movement(db=mock_db, **sample_params)

        # Cache should be updated: 50 + (-5) = 45
        assert existing_cache.current_quantity == Decimal("45.0000")

    @pytest.mark.asyncio
    async def test_does_not_add_new_cache_when_existing(self, mock_db, sample_params):
        """Should NOT add a new cache row when one already exists."""
        existing_cache = StockStatusCache(
            spare_part_id=sample_params["spare_part_id"],
            location_id=sample_params["location_id"],
            current_quantity=Decimal("50.0000"),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_cache
        mock_db.execute = AsyncMock(return_value=mock_result)

        await record_inventory_movement(db=mock_db, **sample_params)

        # db.add should only be called once (for the ledger entry)
        assert mock_db.add.call_count == 1


class TestRecordInventoryMovementReturnsLedgerEntry:
    """Test that the function returns the created ledger entry."""

    @pytest.mark.asyncio
    async def test_returns_ledger_entry(self, mock_db, sample_params):
        """Should return the InventoryMovementLedger instance."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await record_inventory_movement(db=mock_db, **sample_params)

        assert isinstance(result, InventoryMovementLedger)
        assert result.spare_part_id == sample_params["spare_part_id"]

    @pytest.mark.asyncio
    async def test_ledger_entry_has_correct_movement_type(self, mock_db, sample_params):
        """Should preserve the movement_type on the ledger entry."""
        sample_params["movement_type"] = MovementType.TRANSFER_OUT
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await record_inventory_movement(db=mock_db, **sample_params)

        assert result.movement_type == MovementType.TRANSFER_OUT
