"""Unit tests for Notification model and NotificationService.

Tests the Notification model fields, NotificationType enum, and
NotificationService methods including CRUD operations and trigger hooks.

Satisfies Requirements: 3.3, 7.4, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID

from app.models.notification import Notification, NotificationType
from app.models.user import UserRole


# =============================================================================
# NotificationType Enum Tests
# =============================================================================


class TestNotificationType:
    """Test the NotificationType enum values."""

    def test_low_stock_value(self):
        assert NotificationType.LOW_STOCK.value == "low_stock"

    def test_credit_limit_exceeded_value(self):
        assert NotificationType.CREDIT_LIMIT_EXCEEDED.value == "credit_limit_exceeded"

    def test_overdue_customer_value(self):
        assert NotificationType.OVERDUE_CUSTOMER.value == "overdue_customer"

    def test_pending_approval_value(self):
        assert NotificationType.PENDING_APPROVAL.value == "pending_approval"

    def test_system_value(self):
        assert NotificationType.SYSTEM.value == "system"

    def test_all_types_are_strings(self):
        for ntype in NotificationType:
            assert isinstance(ntype.value, str)


# =============================================================================
# Notification Model Tests
# =============================================================================


class TestNotificationModel:
    """Test that the Notification model has the correct columns and types."""

    def test_tablename(self):
        """Notification model should use 'notifications' table name."""
        assert Notification.__tablename__ == "notifications"

    def test_user_id_column_exists(self):
        """Notification should have a required user_id FK column."""
        col = Notification.__table__.columns["user_id"]
        assert col.nullable is False
        # Check FK reference
        fk_names = [fk.target_fullname for fk in col.foreign_keys]
        assert "users.id" in fk_names

    def test_notification_type_column_exists(self):
        """Notification should have a required notification_type column."""
        col = Notification.__table__.columns["notification_type"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_title_column_exists(self):
        """Notification should have a required title column."""
        col = Notification.__table__.columns["title"]
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_message_column_exists(self):
        """Notification should have a required message column."""
        col = Notification.__table__.columns["message"]
        assert isinstance(col.type, Text)
        assert col.nullable is False

    def test_metadata_column_exists(self):
        """Notification should have a nullable metadata JSON column."""
        col = Notification.__table__.columns["metadata"]
        assert isinstance(col.type, JSON)
        assert col.nullable is True

    def test_is_read_column_exists(self):
        """Notification should have a required is_read boolean column."""
        col = Notification.__table__.columns["is_read"]
        assert isinstance(col.type, Boolean)
        assert col.nullable is False

    def test_read_at_column_exists(self):
        """Notification should have a nullable read_at column."""
        col = Notification.__table__.columns["read_at"]
        assert isinstance(col.type, DateTime)
        assert col.nullable is True

    def test_inherits_base_model_columns(self):
        """Notification should have id, created_at, updated_at columns from BaseModel."""
        table_cols = {c.name for c in Notification.__table__.columns}
        assert "id" in table_cols
        assert "created_at" in table_cols
        assert "updated_at" in table_cols
        assert "created_by" in table_cols
        assert "updated_by" in table_cols

    def test_default_is_read_false(self):
        """A new notification should have is_read defaulting to False."""
        col = Notification.__table__.columns["is_read"]
        assert col.default is not None

    def test_default_read_at_none(self):
        """A new notification should have read_at defaulting to None."""
        notification = Notification(
            user_id=uuid.uuid4(),
            notification_type="low_stock",
            title="Test",
            message="Test message",
        )
        assert notification.read_at is None

    def test_mark_as_read(self):
        """mark_as_read() should set is_read=True and read_at to current time."""
        notification = Notification(
            user_id=uuid.uuid4(),
            notification_type="low_stock",
            title="Test",
            message="Test message",
            is_read=False,
        )
        notification.mark_as_read()
        assert notification.is_read is True
        assert notification.read_at is not None
        assert notification.read_at <= datetime.now(timezone.utc)

    def test_repr(self):
        """Notification __repr__ should include id, user_id, type, and is_read."""
        notification = Notification(
            user_id=uuid.uuid4(),
            notification_type="low_stock",
            title="Test",
            message="Test message",
            is_read=False,
        )
        repr_str = repr(notification)
        assert "Notification" in repr_str
        assert "low_stock" in repr_str


# =============================================================================
# NotificationService Tests
# =============================================================================


class TestNotificationServiceCreateNotification:
    """Test NotificationService.create_notification method."""

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
        """Create a NotificationService with mock db."""
        from app.services.notification_service import NotificationService
        return NotificationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_create_notification_basic(self, service, mock_db):
        """Should create a notification with required fields."""
        user_id = uuid.uuid4()

        result = await service.create_notification(
            user_id=user_id,
            notification_type=NotificationType.LOW_STOCK.value,
            title="Low Stock Alert",
            message="Stock is low",
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

        # Verify the notification passed to db.add
        added_notification = mock_db.add.call_args[0][0]
        assert added_notification.user_id == user_id
        assert added_notification.notification_type == "low_stock"
        assert added_notification.title == "Low Stock Alert"
        assert added_notification.message == "Stock is low"
        assert added_notification.is_read is False
        assert added_notification.extra_data is None

    @pytest.mark.asyncio
    async def test_create_notification_with_metadata(self, service, mock_db):
        """Should create a notification with metadata."""
        user_id = uuid.uuid4()
        metadata = {"spare_part_id": str(uuid.uuid4()), "current_quantity": "5"}

        result = await service.create_notification(
            user_id=user_id,
            notification_type=NotificationType.LOW_STOCK.value,
            title="Low Stock",
            message="Stock low",
            metadata=metadata,
        )

        added_notification = mock_db.add.call_args[0][0]
        assert added_notification.extra_data == metadata


class TestNotificationServiceMarkRead:
    """Test NotificationService.mark_read method."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        from app.services.notification_service import NotificationService
        return NotificationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_mark_read_success(self, service, mock_db):
        """Should mark a notification as read."""
        notification_id = uuid.uuid4()
        mock_notification = Notification(
            user_id=uuid.uuid4(),
            notification_type="low_stock",
            title="Test",
            message="Test message",
            is_read=False,
        )
        mock_notification.id = notification_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_notification
        mock_db.execute.return_value = mock_result

        result = await service.mark_read(notification_id)

        assert result.is_read is True
        assert result.read_at is not None

    @pytest.mark.asyncio
    async def test_mark_read_not_found(self, service, mock_db):
        """Should raise NotificationNotFoundError when ID doesn't exist."""
        from app.services.notification_service import NotificationNotFoundError

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotificationNotFoundError):
            await service.mark_read(uuid.uuid4())


class TestNotificationServiceMarkAllRead:
    """Test NotificationService.mark_all_read method."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        from app.services.notification_service import NotificationService
        return NotificationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_mark_all_read_returns_count(self, service, mock_db):
        """Should return the count of updated notifications."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db.execute.return_value = mock_result

        count = await service.mark_all_read(uuid.uuid4())

        assert count == 5
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_all_read_zero_when_none_unread(self, service, mock_db):
        """Should return 0 when no unread notifications exist."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        count = await service.mark_all_read(uuid.uuid4())

        assert count == 0


class TestNotificationServiceGetUserNotifications:
    """Test NotificationService.get_user_notifications method."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        from app.services.notification_service import NotificationService
        return NotificationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_get_user_notifications_returns_tuple(self, service, mock_db):
        """Should return tuple of (notifications, total_count)."""
        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Mock notifications query
        mock_notifications = [MagicMock(), MagicMock()]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_notifications
        mock_notif_result = MagicMock()
        mock_notif_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_notif_result]

        notifications, total = await service.get_user_notifications(uuid.uuid4())

        assert total == 2
        assert len(notifications) == 2

    @pytest.mark.asyncio
    async def test_get_user_notifications_pagination(self, service, mock_db):
        """Should respect page and page_size parameters."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_notif_result = MagicMock()
        mock_notif_result.scalars.return_value = mock_scalars

        mock_db.execute.side_effect = [mock_count_result, mock_notif_result]

        notifications, total = await service.get_user_notifications(
            uuid.uuid4(), page=3, page_size=10
        )

        assert total == 50


# =============================================================================
# Trigger Hook Tests
# =============================================================================


class TestNotificationServiceTriggerLowStock:
    """Test NotificationService.trigger_low_stock_alert method."""

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
        from app.services.notification_service import NotificationService
        return NotificationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_trigger_low_stock_notifies_correct_roles(self, service, mock_db):
        """Should notify Storekeeper and Manager roles (Req 16.1)."""
        # Mock users with correct roles
        storekeeper = MagicMock()
        storekeeper.id = uuid.uuid4()
        storekeeper.role = UserRole.STOREKEEPER.value

        manager = MagicMock()
        manager.id = uuid.uuid4()
        manager.role = UserRole.MANAGER.value

        # First call: _get_users_by_roles
        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = [storekeeper, manager]
        mock_users_result.scalars.return_value = mock_users_scalars

        mock_db.execute.return_value = mock_users_result

        notifications = await service.trigger_low_stock_alert(
            spare_part_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            current_qty=Decimal("3"),
            min_qty=Decimal("10"),
        )

        # Should create 2 notifications (one for each user)
        assert mock_db.add.call_count == 2

        # Verify notification content
        first_notification = mock_db.add.call_args_list[0][0][0]
        assert first_notification.notification_type == "low_stock"
        assert first_notification.title == "Low Stock Alert"
        assert "3" in first_notification.message
        assert "10" in first_notification.message

    @pytest.mark.asyncio
    async def test_trigger_low_stock_includes_metadata(self, service, mock_db):
        """Should include spare_part_id, location_id, quantities in metadata."""
        user = MagicMock()
        user.id = uuid.uuid4()

        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = [user]
        mock_users_result.scalars.return_value = mock_users_scalars
        mock_db.execute.return_value = mock_users_result

        spare_part_id = uuid.uuid4()
        location_id = uuid.uuid4()

        await service.trigger_low_stock_alert(
            spare_part_id=spare_part_id,
            location_id=location_id,
            current_qty=Decimal("2"),
            min_qty=Decimal("5"),
        )

        added_notification = mock_db.add.call_args[0][0]
        assert added_notification.extra_data["spare_part_id"] == str(spare_part_id)
        assert added_notification.extra_data["location_id"] == str(location_id)
        assert added_notification.extra_data["current_quantity"] == "2"
        assert added_notification.extra_data["minimum_quantity"] == "5"


class TestNotificationServiceTriggerCreditLimitExceeded:
    """Test NotificationService.trigger_credit_limit_exceeded method."""

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
        from app.services.notification_service import NotificationService
        return NotificationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_trigger_credit_limit_notifies_manager_admin(self, service, mock_db):
        """Should notify Manager and Admin roles (Req 16.2)."""
        manager = MagicMock()
        manager.id = uuid.uuid4()
        admin = MagicMock()
        admin.id = uuid.uuid4()

        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = [manager, admin]
        mock_users_result.scalars.return_value = mock_users_scalars
        mock_db.execute.return_value = mock_users_result

        await service.trigger_credit_limit_exceeded(
            customer_id=uuid.uuid4(),
            balance=Decimal("55000"),
            limit=Decimal("50000"),
        )

        assert mock_db.add.call_count == 2
        first_notification = mock_db.add.call_args_list[0][0][0]
        assert first_notification.notification_type == "credit_limit_exceeded"
        assert first_notification.title == "Credit Limit Exceeded"


class TestNotificationServiceTriggerOverdueCustomer:
    """Test NotificationService.trigger_overdue_customer method."""

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
        from app.services.notification_service import NotificationService
        return NotificationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_trigger_overdue_customer_notifies_manager_admin(self, service, mock_db):
        """Should notify Manager and Admin roles (Req 16.3)."""
        manager = MagicMock()
        manager.id = uuid.uuid4()

        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = [manager]
        mock_users_result.scalars.return_value = mock_users_scalars
        mock_db.execute.return_value = mock_users_result

        await service.trigger_overdue_customer(
            customer_id=uuid.uuid4(),
            days_overdue=95,
        )

        assert mock_db.add.call_count == 1
        notification = mock_db.add.call_args[0][0]
        assert notification.notification_type == "overdue_customer"
        assert notification.title == "Overdue Customer Alert"
        assert "95" in notification.message
        assert notification.extra_data["days_overdue"] == 95


class TestNotificationServiceTriggerPendingApproval:
    """Test NotificationService.trigger_pending_approval method."""

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
        from app.services.notification_service import NotificationService
        return NotificationService(db=mock_db)

    @pytest.mark.asyncio
    async def test_trigger_pending_approval_notifies_manager_admin(self, service, mock_db):
        """Should notify Manager and Admin roles (Req 16.4)."""
        admin = MagicMock()
        admin.id = uuid.uuid4()

        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = [admin]
        mock_users_result.scalars.return_value = mock_users_scalars
        mock_db.execute.return_value = mock_users_result

        entity_id = uuid.uuid4()
        await service.trigger_pending_approval(
            entity_type="transfer",
            entity_id=entity_id,
            hours_pending=26.5,
        )

        assert mock_db.add.call_count == 1
        notification = mock_db.add.call_args[0][0]
        assert notification.notification_type == "pending_approval"
        assert notification.title == "Pending Approval Reminder"
        assert "transfer" in notification.message
        assert "26.5" in notification.message
        assert notification.extra_data["entity_type"] == "transfer"
        assert notification.extra_data["entity_id"] == str(entity_id)
        assert notification.extra_data["hours_pending"] == 26.5

    @pytest.mark.asyncio
    async def test_trigger_pending_approval_no_users(self, service, mock_db):
        """Should return empty list when no matching users exist."""
        mock_users_result = MagicMock()
        mock_users_scalars = MagicMock()
        mock_users_scalars.all.return_value = []
        mock_users_result.scalars.return_value = mock_users_scalars
        mock_db.execute.return_value = mock_users_result

        notifications = await service.trigger_pending_approval(
            entity_type="purchase_order",
            entity_id=uuid.uuid4(),
            hours_pending=48.0,
        )

        assert notifications == []
        assert mock_db.add.call_count == 0
