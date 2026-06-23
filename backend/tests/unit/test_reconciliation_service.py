"""Unit tests for ReconciliationService.

Tests the reconciliation logic that compares Stock_Status_Cache against
Inventory_Movement_Ledger sums, corrects drift, and generates admin
notifications.

Satisfies Requirements: 18.4, 18.6
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.inventory_movement_ledger import InventoryMovementLedger
from app.models.notification import NotificationType
from app.models.stock_status_cache import StockStatusCache
from app.models.user import User, UserRole
from app.services.reconciliation_service import (
    ReconciliationMismatch,
    ReconciliationResult,
    ReconciliationService,
    run_reconciliation,
)


# =============================================================================
# ReconciliationResult Tests
# =============================================================================


class TestReconciliationResult:
    """Test the ReconciliationResult dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        result = ReconciliationResult()
        assert result.total_cache_entries == 0
        assert result.mismatches_found == 0
        assert result.mismatches_corrected == 0
        assert result.details == []
        assert result.started_at is None
        assert result.completed_at is None

    def test_has_mismatches_false_when_none(self):
        """has_mismatches should be False when mismatches_found is 0."""
        result = ReconciliationResult(mismatches_found=0)
        assert result.has_mismatches is False

    def test_has_mismatches_true_when_nonzero(self):
        """has_mismatches should be True when mismatches_found > 0."""
        result = ReconciliationResult(mismatches_found=3)
        assert result.has_mismatches is True


# =============================================================================
# ReconciliationMismatch Tests
# =============================================================================


class TestReconciliationMismatch:
    """Test the ReconciliationMismatch dataclass."""

    def test_fields_populated(self):
        """Should store all mismatch data."""
        part_id = uuid.uuid4()
        loc_id = uuid.uuid4()
        mismatch = ReconciliationMismatch(
            spare_part_id=part_id,
            location_id=loc_id,
            cached_quantity=Decimal("100"),
            expected_quantity=Decimal("95"),
            drift=Decimal("5"),
        )
        assert mismatch.spare_part_id == part_id
        assert mismatch.location_id == loc_id
        assert mismatch.cached_quantity == Decimal("100")
        assert mismatch.expected_quantity == Decimal("95")
        assert mismatch.drift == Decimal("5")


# =============================================================================
# ReconciliationService Tests
# =============================================================================


class TestReconciliationServiceReconcileStock:
    """Test ReconciliationService.reconcile_stock method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock async database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create a ReconciliationService with mock db."""
        return ReconciliationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_reconcile_empty_cache(self, service, mock_db):
        """Should return immediately with zero totals when cache is empty."""
        # Mock: no cache entries
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await service.reconcile_stock()

        assert result.total_cache_entries == 0
        assert result.mismatches_found == 0
        assert result.mismatches_corrected == 0
        assert result.details == []
        assert result.started_at is not None
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_reconcile_no_mismatches(self, service, mock_db):
        """Should detect no mismatches when cache matches ledger."""
        # Create a cache entry
        cache_entry = MagicMock(spec=StockStatusCache)
        cache_entry.spare_part_id = uuid.uuid4()
        cache_entry.location_id = uuid.uuid4()
        cache_entry.current_quantity = Decimal("50")

        # Mock: get_all_cache_entries returns one entry
        mock_cache_result = MagicMock()
        mock_cache_scalars = MagicMock()
        mock_cache_scalars.all.return_value = [cache_entry]
        mock_cache_result.scalars.return_value = mock_cache_scalars

        # Mock: ledger sum returns matching quantity
        mock_ledger_result = MagicMock()
        mock_ledger_result.scalar.return_value = Decimal("50")

        mock_db.execute.side_effect = [mock_cache_result, mock_ledger_result]

        result = await service.reconcile_stock()

        assert result.total_cache_entries == 1
        assert result.mismatches_found == 0
        assert result.mismatches_corrected == 0

    @pytest.mark.asyncio
    async def test_reconcile_detects_mismatch(self, service, mock_db):
        """Should detect mismatch when cache differs from ledger sum."""
        part_id = uuid.uuid4()
        loc_id = uuid.uuid4()

        cache_entry = MagicMock(spec=StockStatusCache)
        cache_entry.spare_part_id = part_id
        cache_entry.location_id = loc_id
        cache_entry.current_quantity = Decimal("100")

        # Mock: get_all_cache_entries
        mock_cache_result = MagicMock()
        mock_cache_scalars = MagicMock()
        mock_cache_scalars.all.return_value = [cache_entry]
        mock_cache_result.scalars.return_value = mock_cache_scalars

        # Mock: ledger sum returns different quantity (drift detected)
        mock_ledger_result = MagicMock()
        mock_ledger_result.scalar.return_value = Decimal("95")

        # Mock: correction query returns cache entry again
        mock_correction_result = MagicMock()
        mock_correction_result.scalar_one.return_value = cache_entry

        # Mock: admin users query
        admin_user = MagicMock(spec=User)
        admin_user.id = uuid.uuid4()
        admin_user.role = UserRole.ADMIN.value
        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = [admin_user]
        mock_users_result.scalars.return_value = mock_users_scalars

        mock_db.execute.side_effect = [
            mock_cache_result,       # _get_all_cache_entries
            mock_ledger_result,      # _compute_ledger_sum
            mock_correction_result,  # _correct_mismatches (select cache entry)
            mock_users_result,       # _notify_admins_of_drift (get admin users)
        ]

        result = await service.reconcile_stock()

        assert result.total_cache_entries == 1
        assert result.mismatches_found == 1
        assert result.mismatches_corrected == 1
        assert len(result.details) == 1

        mismatch = result.details[0]
        assert mismatch.spare_part_id == part_id
        assert mismatch.location_id == loc_id
        assert mismatch.cached_quantity == Decimal("100")
        assert mismatch.expected_quantity == Decimal("95")
        assert mismatch.drift == Decimal("5")

    @pytest.mark.asyncio
    async def test_reconcile_corrects_cache_entry(self, service, mock_db):
        """Should update cache entry's current_quantity and last_reconciled_at."""
        part_id = uuid.uuid4()
        loc_id = uuid.uuid4()

        cache_entry = MagicMock(spec=StockStatusCache)
        cache_entry.spare_part_id = part_id
        cache_entry.location_id = loc_id
        cache_entry.current_quantity = Decimal("100")

        # Mock: get_all_cache_entries
        mock_cache_result = MagicMock()
        mock_cache_scalars = MagicMock()
        mock_cache_scalars.all.return_value = [cache_entry]
        mock_cache_result.scalars.return_value = mock_cache_scalars

        # Mock: ledger sum (drift of +5)
        mock_ledger_result = MagicMock()
        mock_ledger_result.scalar.return_value = Decimal("95")

        # Mock: correction query - return an actual-like object
        correctable_entry = MagicMock()
        correctable_entry.current_quantity = Decimal("100")
        correctable_entry.last_reconciled_at = None
        mock_correction_result = MagicMock()
        mock_correction_result.scalar_one.return_value = correctable_entry

        # Mock: admin users query (empty - no admins)
        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = []
        mock_users_result.scalars.return_value = mock_users_scalars

        mock_db.execute.side_effect = [
            mock_cache_result,       # _get_all_cache_entries
            mock_ledger_result,      # _compute_ledger_sum
            mock_correction_result,  # _correct_mismatches
            mock_users_result,       # _notify_admins_of_drift
        ]

        await service.reconcile_stock()

        # Verify cache was corrected
        assert correctable_entry.current_quantity == Decimal("95")
        assert correctable_entry.last_reconciled_at is not None
        mock_db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_reconcile_notifies_admins(self, service, mock_db):
        """Should create notifications for admin/manager users on drift."""
        part_id = uuid.uuid4()
        loc_id = uuid.uuid4()

        cache_entry = MagicMock(spec=StockStatusCache)
        cache_entry.spare_part_id = part_id
        cache_entry.location_id = loc_id
        cache_entry.current_quantity = Decimal("50")

        # Mock: get_all_cache_entries
        mock_cache_result = MagicMock()
        mock_cache_scalars = MagicMock()
        mock_cache_scalars.all.return_value = [cache_entry]
        mock_cache_result.scalars.return_value = mock_cache_scalars

        # Mock: ledger sum (drift)
        mock_ledger_result = MagicMock()
        mock_ledger_result.scalar.return_value = Decimal("48")

        # Mock: correction query
        correctable_entry = MagicMock()
        correctable_entry.current_quantity = Decimal("50")
        correctable_entry.last_reconciled_at = None
        mock_correction_result = MagicMock()
        mock_correction_result.scalar_one.return_value = correctable_entry

        # Mock: admin users query
        admin_user = MagicMock(spec=User)
        admin_user.id = uuid.uuid4()
        admin_user.role = UserRole.ADMIN.value
        manager_user = MagicMock(spec=User)
        manager_user.id = uuid.uuid4()
        manager_user.role = UserRole.MANAGER.value
        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = [admin_user, manager_user]
        mock_users_result.scalars.return_value = mock_users_scalars

        mock_db.execute.side_effect = [
            mock_cache_result,       # _get_all_cache_entries
            mock_ledger_result,      # _compute_ledger_sum
            mock_correction_result,  # _correct_mismatches
            mock_users_result,       # _notify_admins_of_drift (get users)
        ]

        await service.reconcile_stock()

        # Notifications should be created (db.add called for each admin user)
        assert mock_db.add.call_count == 2

        # Verify notification content
        first_notification = mock_db.add.call_args_list[0][0][0]
        assert first_notification.notification_type == NotificationType.SYSTEM.value
        assert "Drift Detected" in first_notification.title
        assert "1 mismatch" in first_notification.message

    @pytest.mark.asyncio
    async def test_reconcile_multiple_entries_mixed(self, service, mock_db):
        """Should handle multiple cache entries with some matching and some drifted."""
        part_id_1 = uuid.uuid4()
        loc_id_1 = uuid.uuid4()
        part_id_2 = uuid.uuid4()
        loc_id_2 = uuid.uuid4()

        cache_entry_1 = MagicMock(spec=StockStatusCache)
        cache_entry_1.spare_part_id = part_id_1
        cache_entry_1.location_id = loc_id_1
        cache_entry_1.current_quantity = Decimal("100")  # matches ledger

        cache_entry_2 = MagicMock(spec=StockStatusCache)
        cache_entry_2.spare_part_id = part_id_2
        cache_entry_2.location_id = loc_id_2
        cache_entry_2.current_quantity = Decimal("75")  # drifted from 70

        # Mock: get_all_cache_entries
        mock_cache_result = MagicMock()
        mock_cache_scalars = MagicMock()
        mock_cache_scalars.all.return_value = [cache_entry_1, cache_entry_2]
        mock_cache_result.scalars.return_value = mock_cache_scalars

        # Mock: ledger sums (first matches, second doesn't)
        mock_ledger_result_1 = MagicMock()
        mock_ledger_result_1.scalar.return_value = Decimal("100")

        mock_ledger_result_2 = MagicMock()
        mock_ledger_result_2.scalar.return_value = Decimal("70")

        # Mock: correction query for entry 2
        correctable_entry_2 = MagicMock()
        correctable_entry_2.current_quantity = Decimal("75")
        correctable_entry_2.last_reconciled_at = None
        mock_correction_result = MagicMock()
        mock_correction_result.scalar_one.return_value = correctable_entry_2

        # Mock: admin users query (empty)
        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = []
        mock_users_result.scalars.return_value = mock_users_scalars

        mock_db.execute.side_effect = [
            mock_cache_result,       # _get_all_cache_entries
            mock_ledger_result_1,    # _compute_ledger_sum for entry 1
            mock_ledger_result_2,    # _compute_ledger_sum for entry 2
            mock_correction_result,  # _correct_mismatches for entry 2
            mock_users_result,       # _notify_admins_of_drift
        ]

        result = await service.reconcile_stock()

        assert result.total_cache_entries == 2
        assert result.mismatches_found == 1
        assert result.mismatches_corrected == 1
        assert result.details[0].spare_part_id == part_id_2
        assert result.details[0].drift == Decimal("5")


class TestReconciliationServiceComputeLedgerSum:
    """Test ReconciliationService._compute_ledger_sum method."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return ReconciliationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_compute_ledger_sum_returns_sum(self, service, mock_db):
        """Should return the sum of quantity_change for the part/location."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = Decimal("150.5000")
        mock_db.execute.return_value = mock_result

        total = await service._compute_ledger_sum(uuid.uuid4(), uuid.uuid4())

        assert total == Decimal("150.5000")

    @pytest.mark.asyncio
    async def test_compute_ledger_sum_returns_zero_when_no_entries(self, service, mock_db):
        """Should return Decimal('0') when no ledger entries exist."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute.return_value = mock_result

        total = await service._compute_ledger_sum(uuid.uuid4(), uuid.uuid4())

        assert total == Decimal("0")


class TestReconciliationServiceNotifyAdmins:
    """Test ReconciliationService._notify_admins_of_drift method."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return ReconciliationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_no_notification_when_no_admins(self, service, mock_db):
        """Should not create notifications when no admin/manager users exist."""
        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = []
        mock_users_result.scalars.return_value = mock_users_scalars
        mock_db.execute.return_value = mock_users_result

        mismatches = [
            ReconciliationMismatch(
                spare_part_id=uuid.uuid4(),
                location_id=uuid.uuid4(),
                cached_quantity=Decimal("10"),
                expected_quantity=Decimal("8"),
                drift=Decimal("2"),
            )
        ]

        await service._notify_admins_of_drift(mismatches)

        # No notifications created
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_notification_metadata_limited_to_10(self, service, mock_db):
        """Should limit drift_details in metadata to 10 entries."""
        admin_user = MagicMock(spec=User)
        admin_user.id = uuid.uuid4()
        admin_user.role = UserRole.ADMIN.value

        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = [admin_user]
        mock_users_result.scalars.return_value = mock_users_scalars
        mock_db.execute.return_value = mock_users_result

        # Create 15 mismatches
        mismatches = [
            ReconciliationMismatch(
                spare_part_id=uuid.uuid4(),
                location_id=uuid.uuid4(),
                cached_quantity=Decimal("10"),
                expected_quantity=Decimal("8"),
                drift=Decimal("2"),
            )
            for _ in range(15)
        ]

        await service._notify_admins_of_drift(mismatches)

        # One notification created for the admin
        assert mock_db.add.call_count == 1
        notification = mock_db.add.call_args[0][0]
        assert notification.extra_data["total_mismatches"] == 15
        assert len(notification.extra_data["drift_details"]) == 10


# =============================================================================
# Standalone Function Test
# =============================================================================


class TestRunReconciliation:
    """Test the standalone run_reconciliation function."""

    @pytest.mark.asyncio
    async def test_run_reconciliation_creates_service_and_runs(self):
        """Should create a ReconciliationService and call reconcile_stock."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock: empty cache
        mock_cache_result = MagicMock()
        mock_cache_scalars = MagicMock()
        mock_cache_scalars.all.return_value = []
        mock_cache_result.scalars.return_value = mock_cache_scalars
        mock_db.execute.return_value = mock_cache_result

        result = await run_reconciliation(mock_db)

        assert isinstance(result, ReconciliationResult)
        assert result.total_cache_entries == 0
        assert result.started_at is not None
        assert result.completed_at is not None
