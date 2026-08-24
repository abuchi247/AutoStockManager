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


async def _resolve_entity_statuses(db, notifications) -> dict[str, str]:
    """Look up the current status of referenced entities (transfers, POs).

    Returns a dict of notification_id → current_status_string.
    Only resolves pending_approval notifications that reference an entity.
    """
    from sqlalchemy import select
    from app.models.transfer import Transfer
    from app.models.purchase_order import PurchaseOrder

    result: dict[str, str] = {}

    transfer_ids = []
    po_ids = []
    notification_entity_map: dict[str, tuple[str, str]] = {}  # notification_id → (entity_type, entity_id)

    for n in notifications:
        if n.notification_type != "pending_approval":
            continue
        meta = n.extra_data if isinstance(n.extra_data, dict) else {}
        entity_type = meta.get("entity_type")
        entity_id = meta.get("entity_id")
        if not entity_type or not entity_id:
            continue
        notification_entity_map[str(n.id)] = (entity_type, entity_id)
        if entity_type == "transfer":
            transfer_ids.append(entity_id)
        elif entity_type == "purchase_order":
            po_ids.append(entity_id)

    # Batch fetch transfer statuses
    if transfer_ids:
        from uuid import UUID as UUIDType
        stmt = select(Transfer.id, Transfer.status).filter(
            Transfer.id.in_([UUIDType(tid) for tid in transfer_ids])
        )
        rows = await db.execute(stmt)
        status_map = {str(r.id): r.status.value if hasattr(r.status, 'value') else str(r.status) for r in rows}
        for nid, (etype, eid) in notification_entity_map.items():
            if etype == "transfer" and eid in status_map:
                result[nid] = status_map[eid].lower()

    # Batch fetch PO statuses
    if po_ids:
        from uuid import UUID as UUIDType
        stmt = select(PurchaseOrder.id, PurchaseOrder.status).filter(
            PurchaseOrder.id.in_([UUIDType(pid) for pid in po_ids])
        )
        rows = await db.execute(stmt)
        status_map = {str(r.id): r.status.value if hasattr(r.status, 'value') else str(r.status) for r in rows}
        for nid, (etype, eid) in notification_entity_map.items():
            if etype == "purchase_order" and eid in status_map:
                result[nid] = status_map[eid].lower()

    return result

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

    # Resolve current status for pending_approval notifications
    resolved_statuses = await _resolve_entity_statuses(db, notifications)

    return NotificationListResponse(
        data=[
            NotificationResponse.from_notification(n, resolved_status=resolved_statuses.get(str(n.id)))
            for n in notifications
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
        notification = await service.get_notification(notification_id)
    except NotificationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    # Verify ownership BEFORE mutating state so no DB write occurs for
    # a forbidden request.
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only mark your own notifications as read",
        )

    await service.mark_read(notification_id)
    await db.commit()
    return NotificationResponse.from_notification(notification)


@router.post(
    "/{notification_id}/mark-unread",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark notification as unread",
    description="Mark a single notification as unread. Only the owning user can do this.",
    responses={
        404: {"model": ErrorResponse, "description": "Notification not found"},
        403: {"model": ErrorResponse, "description": "Not your notification"},
    },
)
async def mark_notification_unread(
    notification_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> NotificationResponse:
    """Mark a single notification as unread.

    Allows users to flag a notification they've already read as unread
    so it stays visible as a reminder to take action.
    """
    service = NotificationService(db=db)

    try:
        notification = await service.get_notification(notification_id)
    except NotificationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify your own notifications",
        )

    notification.is_read = False
    notification.read_at = None
    await db.commit()
    return NotificationResponse.from_notification(notification)


@router.post(
    "/check-overdue-suppliers",
    status_code=status.HTTP_200_OK,
    summary="Check for overdue supplier payments",
    description="Scans supplier ledger for overdue payments and creates notifications. Manager/Admin only.",
)
async def check_overdue_suppliers(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Trigger check for overdue supplier payments.

    Creates notifications for managers/admins about suppliers with
    payments past their due date. Deduplicates (once per supplier per day).
    Can be called on dashboard load or via cron.
    """
    from app.models.user import UserRole
    if current_user.role not in (UserRole.MANAGER.value, UserRole.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and admins can trigger overdue checks",
        )

    service = NotificationService(db=db)
    count = await service.check_overdue_supplier_payments()
    await db.commit()
    return {"notified_suppliers": count}
