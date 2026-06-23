"""Notification router for the Auto Spare Parts ERP system.

Provides the following endpoints:
- GET  /api/v1/notifications              - List user's notifications (paginated, filterable)
- POST /api/v1/notifications/{id}/mark-read   - Mark a single notification as read
- POST /api/v1/notifications/mark-all-read    - Mark all notifications as read

All endpoints are accessible by any authenticated user and scoped to
the current user's own notifications.

Satisfies Requirements: 16.5, 16.6
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DbSession
from app.schemas.auth import ErrorResponse
from app.schemas.notification import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
)
from app.services.notification_service import (
    NotificationNotFoundError,
    NotificationService,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List user notifications",
    description="Retrieve a paginated list of the current user's notifications.",
)
async def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(
        default=False, description="If true, only return unread notifications"
    ),
) -> NotificationListResponse:
    """List notifications for the authenticated user.

    Requirement 16.5: Store all notifications with read/unread status per user.
    Supports pagination and filtering by unread status.
    """
    service = NotificationService(db=db)
    notifications, total = await service.get_user_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        page=page,
        page_size=page_size,
    )

    return NotificationListResponse(
        data=[
            NotificationResponse.from_notification(n) for n in notifications
        ],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "/mark-all-read",
    response_model=MarkAllReadResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Mark all unread notifications for the current user as read.",
)
async def mark_all_notifications_read(
    db: DbSession,
    current_user: CurrentUser,
) -> MarkAllReadResponse:
    """Mark all unread notifications as read for the authenticated user.

    Requirement 16.6: Support marking notifications as read in bulk.
    """
    service = NotificationService(db=db)
    count = await service.mark_all_read(user_id=current_user.id)
    await db.commit()

    return MarkAllReadResponse(marked_count=count)


@router.post(
    "/{notification_id}/mark-read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as read",
    description="Mark a single notification as read. Only the owning user can mark their notifications.",
    responses={
        404: {"model": ErrorResponse, "description": "Notification not found"},
        403: {"model": ErrorResponse, "description": "Not your notification"},
    },
)
async def mark_notification_read(
    notification_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> NotificationResponse:
    """Mark a single notification as read.

    Requirement 16.6: Support marking notifications as read individually.
    Only the user who owns the notification can mark it as read.
    """
    service = NotificationService(db=db)

    try:
        notification = await service.mark_read(notification_id)
    except NotificationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    # Verify the notification belongs to the current user
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only mark your own notifications as read",
        )

    await db.commit()
    return NotificationResponse.from_notification(notification)
