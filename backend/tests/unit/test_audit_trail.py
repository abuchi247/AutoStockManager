"""Unit tests for AuditTrail model and AuditTrailService.

Tests the AuditTrail model fields, ActionType enum, and AuditTrailService
methods including record_event, query_events, and immutability enforcement.

Satisfies Requirements: 2.6, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID

from app.models.audit_trail import ActionType, AuditTrail


# =============================================================================
# ActionType Enum Tests
# =============================================================================


class TestActionType:
    """Test the ActionType enum values (Req 15.2)."""

    def test_login_value(self):
        assert ActionType.LOGIN.value == "LOGIN"

    def test_logout_value(self):
        assert ActionType.LOGOUT.value == "LOGOUT"

    def test_create_value(self):
        assert ActionType.CREATE.value == "CREATE"

    def test_update_value(self):
        assert ActionType.UPDATE.value == "UPDATE"

    def test_delete_value(self):
        assert ActionType.DELETE.value == "DELETE"

    def test_approve_value(self):
        assert ActionType.APPROVE.value == "APPROVE"

    def test_payment_value(self):
        assert ActionType.PAYMENT.value == "PAYMENT"

    def test_stock_adjustment_value(self):
        assert ActionType.STOCK_ADJUSTMENT.value == "STOCK_ADJUSTMENT"

    def test_all_types_are_strings(self):
        for action in ActionType:
            assert isinstance(action.value, str)

    def test_covers_all_critical_events(self):
        """Req 15.2: login/logout, CRUD, approval, payment, stock adjustment."""
        expected = {
            "LOGIN", "LOGOUT", "CREATE", "UPDATE", "DELETE",
            "APPROVE", "PAYMENT", "STOCK_ADJUSTMENT",
        }
        actual = {a.value for a in ActionType}
        assert expected == actual


# =============================================================================
# AuditTrail Model Tests
# =============================================================================


class TestAuditTrailModel:
    """Test that the AuditTrail model has the correct columns and constraints."""

    def test_tablename(self):
        """AuditTrail model should use 'audit_trail' table name."""
        assert AuditTrail.__tablename__ == "audit_trail"

    def test_does_not_inherit_base_model(self):
        """AuditTrail should NOT have updated_at or updated_by columns (append-only)."""
        col_names = {c.name for c in AuditTrail.__table__.columns}
        assert "updated_at" not in col_names
        assert "updated_by" not in col_names

    def test_id_column_exists(self):
        """AuditTrail should have a UUID primary key."""
        col = AuditTrail.__table__.columns["id"]
        assert col.primary_key is True

    def test_user_id_column_exists(self):
        """AuditTrail should have a required user_id column."""
        col = AuditTrail.__table__.columns["user_id"]
        assert col.nullable is False

    def test_action_type_column_exists(self):
        """AuditTrail should have a required action_type column."""
        col = AuditTrail.__table__.columns["action_type"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_entity_type_column_exists(self):
        """AuditTrail should have a required entity_type column."""
        col = AuditTrail.__table__.columns["entity_type"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_entity_id_column_nullable(self):
        """AuditTrail entity_id should be nullable (for login/logout events)."""
        col = AuditTrail.__table__.columns["entity_id"]
        assert col.nullable is True

    def test_old_values_column_is_json(self):
        """AuditTrail should have a nullable JSON old_values column (Req 15.4)."""
        col = AuditTrail.__table__.columns["old_values"]
        assert isinstance(col.type, JSON)
        assert col.nullable is True

    def test_new_values_column_is_json(self):
        """AuditTrail should have a nullable JSON new_values column (Req 15.4)."""
        col = AuditTrail.__table__.columns["new_values"]
        assert isinstance(col.type, JSON)
        assert col.nullable is True

    def test_ip_address_column_exists(self):
        """AuditTrail should have a nullable ip_address column."""
        col = AuditTrail.__table__.columns["ip_address"]
        assert isinstance(col.type, String)
        assert col.nullable is True

    def test_created_at_column_exists(self):
        """AuditTrail should have a required created_at timestamp."""
        col = AuditTrail.__table__.columns["created_at"]
        assert isinstance(col.type, DateTime)
        assert col.nullable is False

    def test_has_entity_index(self):
        """AuditTrail should have a composite index on (entity_type, entity_id)."""
        index_names = {idx.name for idx in AuditTrail.__table__.indexes}
        assert "ix_audit_trail_entity" in index_names

    def test_has_user_id_index(self):
        """AuditTrail should have an index on user_id (Req 15.5)."""
        index_names = {idx.name for idx in AuditTrail.__table__.indexes}
        assert "ix_audit_trail_user_id" in index_names

    def test_has_action_type_index(self):
        """AuditTrail should have an index on action_type (Req 15.5)."""
        index_names = {idx.name for idx in AuditTrail.__table__.indexes}
        assert "ix_audit_trail_action_type" in index_names

    def test_has_created_at_index(self):
        """AuditTrail should have an index on created_at (Req 15.5)."""
        index_names = {idx.name for idx in AuditTrail.__table__.indexes}
        assert "ix_audit_trail_created_at" in index_names

    def test_create_instance_with_all_fields(self):
        """Should be able to create an AuditTrail instance with all fields."""
        user_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        entry = AuditTrail(
            user_id=user_id,
            action_type=ActionType.CREATE.value,
            entity_type="spare_part",
            entity_id=entity_id,
            old_values=None,
            new_values={"name": "Brake Pad", "price": "25.00"},
            ip_address="192.168.1.100",
        )
        assert entry.user_id == user_id
        assert entry.action_type == "CREATE"
        assert entry.entity_type == "spare_part"
        assert entry.entity_id == entity_id
        assert entry.old_values is None
        assert entry.new_values == {"name": "Brake Pad", "price": "25.00"}
        assert entry.ip_address == "192.168.1.100"

    def test_create_login_event_without_entity_id(self):
        """Login/logout events should work without entity_id."""
        entry = AuditTrail(
            user_id=uuid.uuid4(),
            action_type=ActionType.LOGIN.value,
            entity_type="session",
            entity_id=None,
            old_values=None,
            new_values=None,
            ip_address="10.0.0.1",
        )
        assert entry.entity_id is None
        assert entry.old_values is None
        assert entry.new_values is None

    def test_repr(self):
        """AuditTrail __repr__ should include key fields."""
        entry = AuditTrail(
            user_id=uuid.uuid4(),
            action_type=ActionType.UPDATE.value,
            entity_type="spare_part",
            entity_id=uuid.uuid4(),
        )
        repr_str = repr(entry)
        assert "AuditTrail" in repr_str
        assert "UPDATE" in repr_str
        assert "spare_part" in repr_str


# =============================================================================
# AuditTrailService Tests - record_event
# =============================================================================


class TestAuditTrailServiceRecordEvent:
    """Test AuditTrailService.record_event method."""

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
        """Create an AuditTrailService with mock db."""
        from app.services.audit_trail_service import AuditTrailService
        return AuditTrailService(db=mock_db)

    @pytest.mark.asyncio
    async def test_record_event_creates_entry(self, service, mock_db):
        """Should create an audit trail entry with all provided fields (Req 15.1)."""
        user_id = uuid.uuid4()
        entity_id = uuid.uuid4()

        result = await service.record_event(
            user_id=user_id,
            action_type=ActionType.CREATE.value,
            entity_type="spare_part",
            entity_id=entity_id,
            old_values=None,
            new_values={"name": "Brake Pad"},
            ip_address="192.168.1.1",
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

        added_entry = mock_db.add.call_args[0][0]
        assert added_entry.user_id == user_id
        assert added_entry.action_type == "CREATE"
        assert added_entry.entity_type == "spare_part"
        assert added_entry.entity_id == entity_id
        assert added_entry.old_values is None
        assert added_entry.new_values == {"name": "Brake Pad"}
        assert added_entry.ip_address == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_record_login_event(self, service, mock_db):
        """Should record login events without entity_id (Req 15.2)."""
        user_id = uuid.uuid4()

        await service.record_event(
            user_id=user_id,
            action_type=ActionType.LOGIN.value,
            entity_type="session",
            entity_id=None,
            ip_address="10.0.0.1",
        )

        added_entry = mock_db.add.call_args[0][0]
        assert added_entry.action_type == "LOGIN"
        assert added_entry.entity_id is None

    @pytest.mark.asyncio
    async def test_record_update_event_with_old_new_values(self, service, mock_db):
        """Should store old/new values for field-level comparison (Req 15.4)."""
        user_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        old_values = {"price": "20.00", "name": "Old Name"}
        new_values = {"price": "25.00", "name": "New Name"}

        await service.record_event(
            user_id=user_id,
            action_type=ActionType.UPDATE.value,
            entity_type="spare_part",
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            ip_address="172.16.0.50",
        )

        added_entry = mock_db.add.call_args[0][0]
        assert added_entry.old_values == old_values
        assert added_entry.new_values == new_values

    @pytest.mark.asyncio
    async def test_record_payment_event(self, service, mock_db):
        """Should record payment events (Req 15.2)."""
        user_id = uuid.uuid4()
        entity_id = uuid.uuid4()

        await service.record_event(
            user_id=user_id,
            action_type=ActionType.PAYMENT.value,
            entity_type="customer_credit_ledger",
            entity_id=entity_id,
            new_values={"amount": "5000.00", "customer_id": str(uuid.uuid4())},
        )

        added_entry = mock_db.add.call_args[0][0]
        assert added_entry.action_type == "PAYMENT"
        assert added_entry.entity_type == "customer_credit_ledger"

    @pytest.mark.asyncio
    async def test_record_stock_adjustment_event(self, service, mock_db):
        """Should record stock adjustment events (Req 15.2)."""
        user_id = uuid.uuid4()
        entity_id = uuid.uuid4()

        await service.record_event(
            user_id=user_id,
            action_type=ActionType.STOCK_ADJUSTMENT.value,
            entity_type="inventory_movement_ledger",
            entity_id=entity_id,
            new_values={"quantity_change": "5", "reason": "audit_adjustment"},
        )

        added_entry = mock_db.add.call_args[0][0]
        assert added_entry.action_type == "STOCK_ADJUSTMENT"

    @pytest.mark.asyncio
    async def test_record_event_without_optional_fields(self, service, mock_db):
        """Should create entry with only required fields."""
        user_id = uuid.uuid4()

        await service.record_event(
            user_id=user_id,
            action_type=ActionType.LOGOUT.value,
            entity_type="session",
        )

        added_entry = mock_db.add.call_args[0][0]
        assert added_entry.user_id == user_id
        assert added_entry.action_type == "LOGOUT"
        assert added_entry.entity_type == "session"
        assert added_entry.entity_id is None
        assert added_entry.old_values is None
        assert added_entry.new_values is None
        assert added_entry.ip_address is None


# =============================================================================
# AuditTrailService Tests - Immutability Enforcement (Req 15.6)
# =============================================================================


class TestAuditTrailServiceImmutability:
    """Test that AuditTrailService enforces append-only semantics."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        from app.services.audit_trail_service import AuditTrailService
        return AuditTrailService(db=mock_db)

    @pytest.mark.asyncio
    async def test_update_raises_immutable_error(self, service):
        """update_event should always raise AuditTrailImmutableError (Req 15.6)."""
        from app.services.audit_trail_service import AuditTrailImmutableError

        with pytest.raises(AuditTrailImmutableError) as exc_info:
            await service.update_event(uuid.uuid4(), {"action_type": "LOGIN"})

        assert "UPDATE" in str(exc_info.value)
        assert "not permitted" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_raises_immutable_error(self, service):
        """delete_event should always raise AuditTrailImmutableError (Req 15.6)."""
        from app.services.audit_trail_service import AuditTrailImmutableError

        with pytest.raises(AuditTrailImmutableError) as exc_info:
            await service.delete_event(uuid.uuid4())

        assert "DELETE" in str(exc_info.value)
        assert "not permitted" in str(exc_info.value)


# =============================================================================
# AuditTrailService Tests - query_events (Req 15.5)
# =============================================================================


class TestAuditTrailServiceQueryEvents:
    """Test AuditTrailService.query_events method."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        from app.services.audit_trail_service import AuditTrailService
        return AuditTrailService(db=mock_db)

    @pytest.mark.asyncio
    async def test_query_events_returns_tuple(self, service, mock_db):
        """Should return tuple of (events, total_count)."""
        from app.services.audit_trail_service import AuditTrailFilters

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        # Mock events query
        mock_events = [MagicMock(), MagicMock(), MagicMock()]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_events
        mock_event_result = MagicMock()
        mock_event_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_event_result]

        filters = AuditTrailFilters()
        events, total = await service.query_events(filters)

        assert total == 3
        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_query_events_with_user_filter(self, service, mock_db):
        """Should support filtering by user_id (Req 15.5)."""
        from app.services.audit_trail_service import AuditTrailFilters

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock()]
        mock_event_result = MagicMock()
        mock_event_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_event_result]

        user_id = uuid.uuid4()
        filters = AuditTrailFilters(user_id=user_id)
        events, total = await service.query_events(filters)

        assert total == 1
        # Verify execute was called (filter applied)
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_query_events_with_all_filters(self, service, mock_db):
        """Should support all filter combinations (Req 15.5)."""
        from app.services.audit_trail_service import AuditTrailFilters

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_event_result = MagicMock()
        mock_event_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_event_result]

        filters = AuditTrailFilters(
            user_id=uuid.uuid4(),
            entity_type="spare_part",
            entity_id=uuid.uuid4(),
            action_type=ActionType.UPDATE.value,
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
            page=2,
            page_size=25,
        )
        events, total = await service.query_events(filters)

        assert total == 0
        assert events == []

    @pytest.mark.asyncio
    async def test_query_events_pagination(self, service, mock_db):
        """Should respect page and page_size parameters."""
        from app.services.audit_trail_service import AuditTrailFilters

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_event_result = MagicMock()
        mock_event_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_event_result]

        filters = AuditTrailFilters(page=5, page_size=10)
        events, total = await service.query_events(filters)

        assert total == 100


# =============================================================================
# AuditTrailService Tests - get_event_by_id
# =============================================================================


class TestAuditTrailServiceGetEventById:
    """Test AuditTrailService.get_event_by_id method."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        from app.services.audit_trail_service import AuditTrailService
        return AuditTrailService(db=mock_db)

    @pytest.mark.asyncio
    async def test_get_event_by_id_found(self, service, mock_db):
        """Should return the audit trail entry when found."""
        mock_entry = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entry
        mock_db.execute.return_value = mock_result

        result = await service.get_event_by_id(uuid.uuid4())
        assert result == mock_entry

    @pytest.mark.asyncio
    async def test_get_event_by_id_not_found(self, service, mock_db):
        """Should return None when no matching entry exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.get_event_by_id(uuid.uuid4())
        assert result is None


# =============================================================================
# AuditTrailFilters Tests
# =============================================================================


class TestAuditTrailFilters:
    """Test AuditTrailFilters initialization and defaults."""

    def test_default_values(self):
        """Should have sensible defaults."""
        from app.services.audit_trail_service import AuditTrailFilters

        filters = AuditTrailFilters()
        assert filters.user_id is None
        assert filters.entity_type is None
        assert filters.entity_id is None
        assert filters.action_type is None
        assert filters.start_date is None
        assert filters.end_date is None
        assert filters.page == 1
        assert filters.page_size == 50

    def test_custom_values(self):
        """Should accept custom filter values."""
        from app.services.audit_trail_service import AuditTrailFilters

        user_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 30, tzinfo=timezone.utc)

        filters = AuditTrailFilters(
            user_id=user_id,
            entity_type="sale",
            entity_id=entity_id,
            action_type="CREATE",
            start_date=start,
            end_date=end,
            page=3,
            page_size=25,
        )
        assert filters.user_id == user_id
        assert filters.entity_type == "sale"
        assert filters.entity_id == entity_id
        assert filters.action_type == "CREATE"
        assert filters.start_date == start
        assert filters.end_date == end
        assert filters.page == 3
        assert filters.page_size == 25
