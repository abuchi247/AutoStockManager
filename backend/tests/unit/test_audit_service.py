"""Unit tests for the AuditService.

Tests validate the snapshot-based audit workflow:
1. initiate_audit - captures Stock_Status_Cache snapshot
2. submit_count - calculates variance against snapshot
3. complete_audit - creates adjustment ledger entries
4. get_reconciliation_view - shows post-snapshot movements
5. check_recount_required - flags parts needing re-count

Satisfies Requirements: 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.models.audit_session import (
    AuditSession,
    AuditSnapshotItem,
    AuditCount,
    AuditType,
    AuditStatus,
)
from app.models.inventory_movement_ledger import (
    InventoryMovementLedger,
    MovementType,
    ReferenceType,
)
from app.models.stock_status_cache import StockStatusCache
from app.services.audit_service import (
    AuditService,
    AuditSessionNotFoundError,
    InvalidAuditStatusError,
    SnapshotItemNotFoundError,
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
def location_id():
    return uuid.uuid4()


@pytest.fixture
def initiated_by():
    return uuid.uuid4()


@pytest.fixture
def approved_by():
    return uuid.uuid4()


@pytest.fixture
def spare_part_id_1():
    return uuid.uuid4()


@pytest.fixture
def spare_part_id_2():
    return uuid.uuid4()


@pytest.fixture
def session_id():
    return uuid.uuid4()


def _make_session(session_id, location_id, status=AuditStatus.INITIATED):
    """Create a mock AuditSession."""
    session = AuditSession(
        location_id=location_id,
        audit_type=AuditType.FULL_STOCK_COUNT,
        status=status,
        snapshot_timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
        initiated_by=uuid.uuid4(),
    )
    session.id = session_id
    return session


def _mock_scalar_one_or_none(mock_db, obj):
    """Configure mock_db.execute to return obj via scalar_one_or_none."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = obj
    mock_db.execute = AsyncMock(return_value=mock_result)


def _mock_execute_sequence(mock_db, results):
    """Configure mock_db.execute to return different results on each call."""
    mock_results = []
    for r in results:
        mock_res = MagicMock()
        if isinstance(r, list):
            mock_res.scalars.return_value.all.return_value = r
            mock_res.all.return_value = r
        else:
            mock_res.scalar_one_or_none.return_value = r
            mock_res.scalar.return_value = r
        mock_results.append(mock_res)
    mock_db.execute = AsyncMock(side_effect=mock_results)


# =============================================================================
# Tests: initiate_audit
# =============================================================================


class TestInitiateAudit:
    """Test that initiate_audit captures snapshots correctly."""

    @pytest.mark.asyncio
    async def test_creates_session_with_correct_attributes(
        self, mock_db, location_id, initiated_by
    ):
        """Should create an AuditSession with correct fields."""
        # Mock execute to return empty cache (no parts at location)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = AuditService(db=mock_db)
        result = await service.initiate_audit(
            location_id=location_id,
            audit_type=AuditType.FULL_STOCK_COUNT,
            initiated_by=initiated_by,
        )

        # Verify session was added
        add_calls = mock_db.add.call_args_list
        session_adds = [
            c[0][0] for c in add_calls
            if isinstance(c[0][0], AuditSession)
        ]
        assert len(session_adds) == 1
        session = session_adds[0]
        assert session.location_id == location_id
        assert session.audit_type == AuditType.FULL_STOCK_COUNT
        assert session.status == AuditStatus.INITIATED
        assert session.initiated_by == initiated_by
        assert session.snapshot_timestamp is not None

    @pytest.mark.asyncio
    async def test_captures_snapshot_for_all_parts_full_audit(
        self, mock_db, location_id, initiated_by, spare_part_id_1, spare_part_id_2
    ):
        """FULL_STOCK_COUNT should capture all parts at the location."""
        cache1 = StockStatusCache(
            spare_part_id=spare_part_id_1,
            location_id=location_id,
            current_quantity=Decimal("100.0000"),
        )
        cache2 = StockStatusCache(
            spare_part_id=spare_part_id_2,
            location_id=location_id,
            current_quantity=Decimal("50.0000"),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [cache1, cache2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = AuditService(db=mock_db)
        await service.initiate_audit(
            location_id=location_id,
            audit_type=AuditType.FULL_STOCK_COUNT,
            initiated_by=initiated_by,
        )

        # Should create 2 snapshot items
        add_calls = mock_db.add.call_args_list
        snapshot_adds = [
            c[0][0] for c in add_calls
            if isinstance(c[0][0], AuditSnapshotItem)
        ]
        assert len(snapshot_adds) == 2
        quantities = {s.snapshot_quantity for s in snapshot_adds}
        assert Decimal("100.0000") in quantities
        assert Decimal("50.0000") in quantities


# =============================================================================
# Tests: submit_count
# =============================================================================


class TestSubmitCount:
    """Test that submit_count calculates variance against snapshot."""

    @pytest.mark.asyncio
    async def test_calculates_positive_variance(
        self, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Variance should be positive when counted > snapshot."""
        session = _make_session(session_id, location_id)
        snapshot_item = AuditSnapshotItem(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            snapshot_quantity=Decimal("100.0000"),
        )

        # First call returns session, second returns snapshot_item
        _mock_execute_sequence(mock_db, [session, snapshot_item])

        service = AuditService(db=mock_db)
        result = await service.submit_count(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            counted_quantity=Decimal("110.0000"),
            counted_by=uuid.uuid4(),
        )

        # Verify AuditCount was added with correct variance
        add_calls = mock_db.add.call_args_list
        count_adds = [
            c[0][0] for c in add_calls
            if isinstance(c[0][0], AuditCount)
        ]
        assert len(count_adds) == 1
        assert count_adds[0].variance == Decimal("10.0000")
        assert count_adds[0].counted_quantity == Decimal("110.0000")

    @pytest.mark.asyncio
    async def test_calculates_negative_variance(
        self, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Variance should be negative when counted < snapshot."""
        session = _make_session(session_id, location_id)
        snapshot_item = AuditSnapshotItem(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            snapshot_quantity=Decimal("100.0000"),
        )
        _mock_execute_sequence(mock_db, [session, snapshot_item])

        service = AuditService(db=mock_db)
        await service.submit_count(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            counted_quantity=Decimal("90.0000"),
            counted_by=uuid.uuid4(),
        )

        add_calls = mock_db.add.call_args_list
        count_adds = [
            c[0][0] for c in add_calls
            if isinstance(c[0][0], AuditCount)
        ]
        assert count_adds[0].variance == Decimal("-10.0000")

    @pytest.mark.asyncio
    async def test_zero_variance_when_count_matches_snapshot(
        self, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Variance should be zero when counted == snapshot."""
        session = _make_session(session_id, location_id)
        snapshot_item = AuditSnapshotItem(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            snapshot_quantity=Decimal("100.0000"),
        )
        _mock_execute_sequence(mock_db, [session, snapshot_item])

        service = AuditService(db=mock_db)
        await service.submit_count(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            counted_quantity=Decimal("100.0000"),
            counted_by=uuid.uuid4(),
        )

        add_calls = mock_db.add.call_args_list
        count_adds = [
            c[0][0] for c in add_calls
            if isinstance(c[0][0], AuditCount)
        ]
        assert count_adds[0].variance == Decimal("0.0000")

    @pytest.mark.asyncio
    async def test_rejects_completed_session(
        self, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Should raise InvalidAuditStatusError for COMPLETED sessions."""
        session = _make_session(
            session_id, location_id, status=AuditStatus.COMPLETED
        )
        _mock_scalar_one_or_none(mock_db, session)

        service = AuditService(db=mock_db)
        with pytest.raises(InvalidAuditStatusError):
            await service.submit_count(
                session_id=session_id,
                spare_part_id=spare_part_id_1,
                counted_quantity=Decimal("10.0000"),
                counted_by=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_rejects_missing_snapshot_item(
        self, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Should raise SnapshotItemNotFoundError if part not in snapshot."""
        session = _make_session(session_id, location_id)
        _mock_execute_sequence(mock_db, [session, None])

        service = AuditService(db=mock_db)
        with pytest.raises(SnapshotItemNotFoundError):
            await service.submit_count(
                session_id=session_id,
                spare_part_id=spare_part_id_1,
                counted_quantity=Decimal("10.0000"),
                counted_by=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_transitions_initiated_to_in_progress(
        self, mock_db, session_id, location_id, spare_part_id_1
    ):
        """First count should transition session from INITIATED to IN_PROGRESS."""
        session = _make_session(session_id, location_id, AuditStatus.INITIATED)
        snapshot_item = AuditSnapshotItem(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            snapshot_quantity=Decimal("100.0000"),
        )
        _mock_execute_sequence(mock_db, [session, snapshot_item])

        service = AuditService(db=mock_db)
        await service.submit_count(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            counted_quantity=Decimal("95.0000"),
            counted_by=uuid.uuid4(),
        )

        assert session.status == AuditStatus.IN_PROGRESS


# =============================================================================
# Tests: complete_audit
# =============================================================================


class TestCompleteAudit:
    """Test that complete_audit creates adjustment ledger entries."""

    @pytest.mark.asyncio
    @patch(
        "app.services.audit_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_creates_adjustment_for_nonzero_variance(
        self, mock_record, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Should create ledger adjustment for non-zero variance."""
        session = _make_session(
            session_id, location_id, status=AuditStatus.IN_PROGRESS
        )
        count = AuditCount(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            counted_quantity=Decimal("95.0000"),
            variance=Decimal("-5.0000"),
            counted_by=uuid.uuid4(),
            counted_at=datetime.now(timezone.utc),
        )
        _mock_execute_sequence(mock_db, [session, [count]])

        service = AuditService(db=mock_db)
        approved_by = uuid.uuid4()
        result = await service.complete_audit(session_id, approved_by)

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args.kwargs
        assert call_kwargs["spare_part_id"] == spare_part_id_1
        assert call_kwargs["location_id"] == location_id
        assert call_kwargs["quantity_change"] == Decimal("-5.0000")
        assert call_kwargs["movement_type"] == MovementType.ADJUSTMENT.value
        assert call_kwargs["reference_type"] == ReferenceType.AUDIT.value
        assert call_kwargs["reference_id"] == session_id

    @pytest.mark.asyncio
    @patch(
        "app.services.audit_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_skips_zero_variance(
        self, mock_record, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Should NOT create ledger entry for zero variance."""
        session = _make_session(
            session_id, location_id, status=AuditStatus.IN_PROGRESS
        )
        count = AuditCount(
            session_id=session_id,
            spare_part_id=spare_part_id_1,
            counted_quantity=Decimal("100.0000"),
            variance=Decimal("0"),
            counted_by=uuid.uuid4(),
            counted_at=datetime.now(timezone.utc),
        )
        _mock_execute_sequence(mock_db, [session, [count]])

        service = AuditService(db=mock_db)
        await service.complete_audit(session_id, uuid.uuid4())

        mock_record.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "app.services.audit_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_sets_session_to_completed(
        self, mock_record, mock_db, session_id, location_id
    ):
        """Should set session status to COMPLETED."""
        session = _make_session(
            session_id, location_id, status=AuditStatus.IN_PROGRESS
        )
        _mock_execute_sequence(mock_db, [session, []])

        service = AuditService(db=mock_db)
        approved_by = uuid.uuid4()
        result = await service.complete_audit(session_id, approved_by)

        assert session.status == AuditStatus.COMPLETED
        assert session.approved_by == approved_by
        assert session.completed_at is not None

    @pytest.mark.asyncio
    @patch(
        "app.services.audit_service.record_inventory_movement",
        new_callable=AsyncMock,
    )
    async def test_rejects_already_completed_session(
        self, mock_record, mock_db, session_id, location_id
    ):
        """Should raise InvalidAuditStatusError for COMPLETED sessions."""
        session = _make_session(
            session_id, location_id, status=AuditStatus.COMPLETED
        )
        _mock_scalar_one_or_none(mock_db, session)

        service = AuditService(db=mock_db)
        with pytest.raises(InvalidAuditStatusError):
            await service.complete_audit(session_id, uuid.uuid4())


# =============================================================================
# Tests: get_reconciliation_view
# =============================================================================


class TestGetReconciliationView:
    """Test that reconciliation view returns post-snapshot movements."""

    @pytest.mark.asyncio
    async def test_returns_post_snapshot_movements(
        self, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Should return movements that occurred after the snapshot."""
        session = _make_session(session_id, location_id)
        entry = InventoryMovementLedger(
            spare_part_id=spare_part_id_1,
            location_id=location_id,
            quantity_change=Decimal("-5.0000"),
            movement_type=MovementType.SALE.value,
            reference_type=ReferenceType.SALE.value,
            reference_id=uuid.uuid4(),
            unit_cost=Decimal("100.0000"),
            created_by=uuid.uuid4(),
        )
        entry.id = uuid.uuid4()
        entry.created_at = datetime.now(timezone.utc)

        # First call returns session, second returns ledger entries
        _mock_execute_sequence(mock_db, [session, [entry]])

        service = AuditService(db=mock_db)
        result = await service.get_reconciliation_view(session_id)

        assert len(result) == 1
        assert result[0].spare_part_id == spare_part_id_1
        assert result[0].quantity_change == Decimal("-5.0000")
        assert result[0].movement_type == MovementType.SALE.value

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_movements(
        self, mock_db, session_id, location_id
    ):
        """Should return empty list if no post-snapshot movements."""
        session = _make_session(session_id, location_id)
        _mock_execute_sequence(mock_db, [session, []])

        service = AuditService(db=mock_db)
        result = await service.get_reconciliation_view(session_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_session(self, mock_db):
        """Should raise AuditSessionNotFoundError if session not found."""
        _mock_scalar_one_or_none(mock_db, None)

        service = AuditService(db=mock_db)
        with pytest.raises(AuditSessionNotFoundError):
            await service.get_reconciliation_view(uuid.uuid4())


# =============================================================================
# Tests: check_recount_required
# =============================================================================


class TestCheckRecountRequired:
    """Test that check_recount_required flags parts with post-snapshot movements."""

    @pytest.mark.asyncio
    async def test_flags_parts_with_movements(
        self, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Should flag spare parts that had movements after snapshot."""
        session = _make_session(session_id, location_id)

        # Mock: first call returns session, second returns snapshot part ids,
        # third returns grouped movements
        mock_results = []

        # Session lookup
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = session
        mock_results.append(r1)

        # Snapshot part IDs
        r2 = MagicMock()
        r2.all.return_value = [(spare_part_id_1,)]
        mock_results.append(r2)

        # Grouped ledger movements
        r3 = MagicMock()
        r3.all.return_value = [
            (spare_part_id_1, 2, Decimal("-10.0000"))
        ]
        mock_results.append(r3)

        mock_db.execute = AsyncMock(side_effect=mock_results)

        service = AuditService(db=mock_db)
        result = await service.check_recount_required(session_id)

        assert len(result) == 1
        assert result[0].spare_part_id == spare_part_id_1
        assert result[0].movement_count == 2
        assert result[0].net_quantity_change == Decimal("-10.0000")

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_movements(
        self, mock_db, session_id, location_id, spare_part_id_1
    ):
        """Should return empty list if no post-snapshot movements."""
        session = _make_session(session_id, location_id)

        mock_results = []
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = session
        mock_results.append(r1)

        r2 = MagicMock()
        r2.all.return_value = [(spare_part_id_1,)]
        mock_results.append(r2)

        r3 = MagicMock()
        r3.all.return_value = []
        mock_results.append(r3)

        mock_db.execute = AsyncMock(side_effect=mock_results)

        service = AuditService(db=mock_db)
        result = await service.check_recount_required(session_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_snapshot_items(
        self, mock_db, session_id, location_id
    ):
        """Should return empty list if audit has no snapshot items."""
        session = _make_session(session_id, location_id)

        mock_results = []
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = session
        mock_results.append(r1)

        r2 = MagicMock()
        r2.all.return_value = []
        mock_results.append(r2)

        mock_db.execute = AsyncMock(side_effect=mock_results)

        service = AuditService(db=mock_db)
        result = await service.check_recount_required(session_id)

        assert result == []
