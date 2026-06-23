"""
Notification service for the Auto Spare Parts ERP system.

Provides notification creation, read-status management, paginated retrieval,
and trigger hooks for system events (low stock, credit limit exceeded,
overdue customers, pending approvals).

Satisfies Requirements:
- 3.3: Low stock alert when spare part falls below minimum level
- 7.4: Overdue customer notification (90+ days)
- 16.1: Low stock notification for Storekeeper and Manager roles
- 16.2: Credit limit exceeded notification for Manager and Admin roles
- 16.3: Overdue customer notification for Manager and Admin roles
- 16.4: Pending approval reminder (24+ hours) for Manager and Admin
- 16.5: Store all notifications with read/unread status per user
- 16.6: Support marking notifications as read individually or in bulk
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole


# =============================================================================
# Custom Exceptions
# =============================================================================


class NotificationNotFoundError(Exception):
    """Raised when a notification with the given ID is not found."""

    def __init__(self, notification_id: UUID):
        self.message = f"Notification with ID '{notification_id}' not found"
        super().__init__(self.message)


# =============================================================================
# Notification Service
# =============================================================================


class NotificationService:
    """Service handling notification CRUD and trigger hooks.

    Provides methods to create notifications, mark them as read (individually
    or in bulk), retrieve paginated notification lists, and trigger
    notifications for specific system events.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the notification service.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db

    # -------------------------------------------------------------------------
    # Core CRUD Operations
    # -------------------------------------------------------------------------

    async def create_notification(
        self,
        user_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        metadata: Optional[dict] = None,
    ) -> Notification:
        """Create a new notification for a user.

        Satisfies Requirement 16.5: Store all notifications with read/unread
        status per user.

        Args:
            user_id: UUID of the user to notify.
            notification_type: Type of notification (from NotificationType enum).
            title: Short notification title.
            message: Full notification message.
            metadata: Optional JSON metadata with additional context.

        Returns:
            The newly created Notification instance.
        """
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            extra_data=metadata,
            is_read=False,
        )
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def mark_read(self, notification_id: UUID) -> Notification:
        """Mark a single notification as read.

        Satisfies Requirement 16.6: Support marking notifications as read
        individually.

        Args:
            notification_id: UUID of the notification to mark as read.

        Returns:
            The updated Notification instance.

        Raises:
            NotificationNotFoundError: If no notification with that ID exists.
        """
        stmt = select(Notification).filter(Notification.id == notification_id)
        result = await self.db.execute(stmt)
        notification = result.scalar_one_or_none()

        if notification is None:
            raise NotificationNotFoundError(notification_id)

        notification.mark_as_read()
        await self.db.flush()
        return notification

    async def mark_all_read(self, user_id: UUID) -> int:
        """Mark all unread notifications as read for a user.

        Satisfies Requirement 16.6: Support marking notifications as read
        in bulk.

        Args:
            user_id: UUID of the user whose notifications to mark as read.

        Returns:
            The number of notifications that were marked as read.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True, read_at=now)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount

    async def get_user_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Notification], int]:
        """Get paginated notifications for a user.

        Args:
            user_id: UUID of the user.
            unread_only: If True, only return unread notifications.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (list of notifications, total count).
        """
        filters = [Notification.user_id == user_id]

        if unread_only:
            filters.append(Notification.is_read == False)  # noqa: E712

        # Count total
        count_stmt = select(func.count(Notification.id)).filter(*filters)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated results (newest first)
        offset = (page - 1) * page_size
        stmt = (
            select(Notification)
            .filter(*filters)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        notifications = list(result.scalars().all())

        return notifications, total

    # -------------------------------------------------------------------------
    # Trigger Hooks
    # -------------------------------------------------------------------------

    async def _get_users_by_roles(self, roles: list[str]) -> list[User]:
        """Get all active users with the specified roles.

        Args:
            roles: List of role values to filter by.

        Returns:
            List of active User instances matching the roles.
        """
        stmt = select(User).filter(
            User.role.in_(roles),
            User.is_active == True,  # noqa: E712
            User.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def trigger_low_stock_alert(
        self,
        spare_part_id: UUID,
        location_id: UUID,
        current_qty: Decimal,
        min_qty: Decimal,
    ) -> list[Notification]:
        """Trigger low stock notifications for Storekeeper and Manager roles.

        Satisfies Requirements 3.3 and 16.1: THE Inventory_Manager SHALL
        trigger a Low_Stock_Alert when any spare part's quantity falls below
        its minimum stock level, notifying Storekeeper and Manager roles.

        Args:
            spare_part_id: UUID of the spare part with low stock.
            location_id: UUID of the location where stock is low.
            current_qty: Current stock quantity.
            min_qty: Minimum stock level threshold.

        Returns:
            List of created Notification instances.
        """
        target_roles = [UserRole.STOREKEEPER.value, UserRole.MANAGER.value]
        users = await self._get_users_by_roles(target_roles)

        notifications = []
        for user in users:
            notification = await self.create_notification(
                user_id=user.id,
                notification_type=NotificationType.LOW_STOCK.value,
                title="Low Stock Alert",
                message=(
                    f"Stock level ({current_qty}) has fallen below minimum "
                    f"level ({min_qty}). Please reorder."
                ),
                metadata={
                    "spare_part_id": str(spare_part_id),
                    "location_id": str(location_id),
                    "current_quantity": str(current_qty),
                    "minimum_quantity": str(min_qty),
                },
            )
            notifications.append(notification)

        return notifications

    async def trigger_credit_limit_exceeded(
        self,
        customer_id: UUID,
        balance: Decimal,
        limit: Decimal,
    ) -> list[Notification]:
        """Trigger credit limit exceeded notifications for Manager and Admin roles.

        Satisfies Requirement 16.2: THE Notification_System SHALL send a
        Credit_Limit_Exceeded notification to Manager and Admin roles when
        a customer's balance exceeds their credit limit.

        Args:
            customer_id: UUID of the customer who exceeded their limit.
            balance: Current outstanding balance.
            limit: Credit limit that was exceeded.

        Returns:
            List of created Notification instances.
        """
        target_roles = [UserRole.MANAGER.value, UserRole.ADMIN.value]
        users = await self._get_users_by_roles(target_roles)

        notifications = []
        for user in users:
            notification = await self.create_notification(
                user_id=user.id,
                notification_type=NotificationType.CREDIT_LIMIT_EXCEEDED.value,
                title="Credit Limit Exceeded",
                message=(
                    f"Customer balance ({balance}) has exceeded the credit "
                    f"limit ({limit}). Immediate attention required."
                ),
                metadata={
                    "customer_id": str(customer_id),
                    "current_balance": str(balance),
                    "credit_limit": str(limit),
                },
            )
            notifications.append(notification)

        return notifications

    async def trigger_overdue_customer(
        self,
        customer_id: UUID,
        days_overdue: int,
    ) -> list[Notification]:
        """Trigger overdue customer notifications for Manager and Admin roles.

        Satisfies Requirements 7.4 and 16.3: THE Notification_System SHALL
        send an Overdue_Customer notification to Manager and Admin roles when
        a customer has outstanding balance for 90+ days.

        Args:
            customer_id: UUID of the overdue customer.
            days_overdue: Number of days the customer is overdue.

        Returns:
            List of created Notification instances.
        """
        target_roles = [UserRole.MANAGER.value, UserRole.ADMIN.value]
        users = await self._get_users_by_roles(target_roles)

        notifications = []
        for user in users:
            notification = await self.create_notification(
                user_id=user.id,
                notification_type=NotificationType.OVERDUE_CUSTOMER.value,
                title="Overdue Customer Alert",
                message=(
                    f"Customer has an outstanding balance overdue by "
                    f"{days_overdue} days. Follow-up action required."
                ),
                metadata={
                    "customer_id": str(customer_id),
                    "days_overdue": days_overdue,
                },
            )
            notifications.append(notification)

        return notifications

    async def trigger_pending_approval(
        self,
        entity_type: str,
        entity_id: UUID,
        hours_pending: float,
    ) -> list[Notification]:
        """Trigger pending approval reminder for Manager and Admin roles.

        Satisfies Requirement 16.4: THE Notification_System SHALL send a
        Pending_Approval_Reminder to Manager and Admin roles when an
        approval request has been pending for more than 24 hours.

        Args:
            entity_type: Type of entity awaiting approval (e.g., 'transfer', 'purchase_order').
            entity_id: UUID of the entity awaiting approval.
            hours_pending: Number of hours the approval has been pending.

        Returns:
            List of created Notification instances.
        """
        target_roles = [UserRole.MANAGER.value, UserRole.ADMIN.value]
        users = await self._get_users_by_roles(target_roles)

        notifications = []
        for user in users:
            notification = await self.create_notification(
                user_id=user.id,
                notification_type=NotificationType.PENDING_APPROVAL.value,
                title="Pending Approval Reminder",
                message=(
                    f"A {entity_type} has been pending approval for "
                    f"{hours_pending:.1f} hours. Please review."
                ),
                metadata={
                    "entity_type": entity_type,
                    "entity_id": str(entity_id),
                    "hours_pending": hours_pending,
                },
            )
            notifications.append(notification)

        return notifications
