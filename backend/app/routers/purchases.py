"""Purchase order router for purchasing and goods receipt endpoints.

Provides the following endpoints:
- GET    /api/v1/purchase-orders              - List POs (paginated, filterable)
- POST   /api/v1/purchase-orders              - Create a PO in DRAFT status
- GET    /api/v1/purchase-orders/{id}         - Get single PO
- POST   /api/v1/purchase-orders/{id}/approve - Approve PO (Manager, Admin)
- POST   /api/v1/purchase-orders/{id}/receive - Receive goods / GRN (SK, Mgr, Admin)
- POST   /api/v1/purchase-orders/{id}/cancel  - Cancel PO (Manager, Admin)

Satisfies Requirements: 9.1, 9.3, 9.4, 9.7
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.services.permission_service import require_permission
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.grn import GRNResponse
from app.schemas.purchase_order import (
    GoodsReceiveRequest,
    PurchaseOrderCancel,
    PurchaseOrderCreate,
    PurchaseOrderListResponse,
    PurchaseOrderResponse,
)
from app.services.purchase_service import (
    CancellationReasonRequiredError,
    InvalidGRNQuantityError,
    InvalidPOStatusError,
    POHasNoItemsError,
    PurchaseOrderNotFoundError,
    PurchaseService,
)

router = APIRouter(prefix="/api/v1/purchase-orders", tags=["Purchases"])


def _get_purchase_service(db: AsyncSession, user_id: UUID) -> PurchaseService:
    """Create a PurchaseService instance."""
    return PurchaseService(db=db, user_id=user_id)


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=PurchaseOrderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List purchase orders",
    description="Retrieve a paginated list of purchase orders, optionally filtered by supplier or status. Manager and Admin only.",
)
async def list_purchase_orders(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    supplier_id: Optional[UUID] = Query(
        default=None,
        description="Filter by supplier UUID",
    ),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by PO status (DRAFT, APPROVED, ORDERED, PARTIALLY_RECEIVED, RECEIVED, CANCELLED)",
    ),
) -> PurchaseOrderListResponse:
    """List all purchase orders with optional filtering and pagination.

    Accessible by Manager and Admin roles.
    """
    service = _get_purchase_service(db, current_user.id)

    # Convert status string to enum if provided
    po_status = None
    if status_filter:
        try:
            po_status = PurchaseOrderStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}. Valid values: {[s.value for s in PurchaseOrderStatus]}",
            )

    pos, total = await service.list_pos(
        supplier_id=supplier_id,
        status=po_status,
        page=page,
        page_size=page_size,
    )

    return PurchaseOrderListResponse(
        data=[PurchaseOrderResponse.model_validate(po) for po in pos],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a purchase order",
    description="Create a new purchase order in DRAFT status. Manager or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    },
)
async def create_purchase_order(
    request: PurchaseOrderCreate,
    db: DbSession,
    current_user: User = Depends(
        require_permission("purchasing")
    ),
) -> PurchaseOrderResponse:
    """Create a new purchase order in DRAFT status.

    Requirements:
    - 9.1: PO supports draft, approved, ordered, partially_received, received, cancelled states
    - 9.2: Initial state is DRAFT
    """
    service = _get_purchase_service(db, current_user.id)

    items = [
        {
            "spare_part_id": item.spare_part_id,
            "quantity_ordered": item.quantity_ordered,
            "unit_cost": item.unit_cost,
        }
        for item in request.items
    ]

    po = await service.create_po(
        supplier_id=request.supplier_id,
        items=items,
        notes=request.notes,
    )
    await db.commit()
    await db.refresh(po)

    # Notify managers/admins that a new PO needs approval
    from app.services.notification_service import NotificationService
    from app.models.supplier import Supplier
    supplier_result = await db.execute(select(Supplier.name).filter(Supplier.id == request.supplier_id))
    supplier_name = supplier_result.scalar_one_or_none() or "Unknown"
    notification_service = NotificationService(db=db)
    await notification_service.trigger_pending_approval(
        entity_type="purchase_order",
        entity_id=po.id,
        hours_pending=0,
    )
    await db.commit()

    return PurchaseOrderResponse.model_validate(po)


@router.get(
    "/{po_id}",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get purchase order by ID",
    description="Retrieve a single purchase order with its line items.",
    responses={
        404: {"model": ErrorResponse, "description": "Purchase order not found"},
    },
)
async def get_purchase_order(
    po_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> PurchaseOrderResponse:
    """Get a single purchase order by its ID.

    Accessible by Manager and Admin roles.
    """
    service = _get_purchase_service(db, current_user.id)

    try:
        po = await service.get_po(po_id)
        # Eagerly load supplier and spare_part for items
        stmt = (
            select(PurchaseOrder)
            .filter_by(id=po_id)
            .options(
                selectinload(PurchaseOrder.supplier),
                selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.spare_part),
            )
        )
        result = await db.execute(stmt)
        po = result.scalar_one()
        return PurchaseOrderResponse.model_validate(po)
    except PurchaseOrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )


@router.post(
    "/{po_id}/approve",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve a purchase order",
    description="Approve a DRAFT purchase order, changing its status to APPROVED. Manager or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid PO state or no items"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Purchase order not found"},
    },
)
async def approve_purchase_order(
    po_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_permission("purchasing")
    ),
) -> PurchaseOrderResponse:
    """Approve a purchase order (DRAFT → APPROVED).

    Requirements:
    - 9.3: Manager/Admin approves PO, changing state from draft to approved
    """
    service = _get_purchase_service(db, current_user.id)

    try:
        po = await service.approve_po(
            po_id=po_id,
            approved_by=current_user.id,
        )
        await db.commit()
        await db.refresh(po)
        return PurchaseOrderResponse.model_validate(po)
    except PurchaseOrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )
    except InvalidPOStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except POHasNoItemsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{po_id}/receive",
    response_model=GRNResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive goods against a purchase order",
    description="Create a Goods Receipt Note (GRN) recording received quantities. Creates cost layers and updates stock. Storekeeper, Manager, or Admin.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid PO state or quantity exceeds remaining"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Purchase order not found"},
    },
)
async def receive_goods(
    po_id: UUID,
    request: GoodsReceiveRequest,
    db: DbSession,
    current_user: User = Depends(
        require_permission("receiving")
    ),
) -> GRNResponse:
    """Receive goods against a purchase order, creating a GRN.

    Requirements:
    - 9.4: Goods received creates GRN recording received quantities per line item
    - 9.5: GRN confirmation adds received quantities to location via ledger
    - 9.6: Updates PO state to partially_received or received
    """
    service = _get_purchase_service(db, current_user.id)

    items = [
        {
            "po_item_id": item.po_item_id,
            "quantity_received": item.quantity_received,
            **({"unit_cost": item.unit_cost} if item.unit_cost is not None else {}),
        }
        for item in request.items
    ]

    try:
        grn = await service.receive_goods(
            po_id=po_id,
            location_id=request.location_id,
            received_by=current_user.id,
            items=items,
            notes=request.notes,
        )

        # Check for quantity discrepancies and notify managers
        from app.services.notification_service import NotificationService
        from app.models.notification import NotificationType
        from app.models.supplier import Supplier
        from decimal import Decimal

        notification_service = NotificationService(db=db)

        # Get PO with items for discrepancy check
        po_stmt = (
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items))
            .filter(PurchaseOrder.id == po_id)
        )
        po_result = await db.execute(po_stmt)
        po = po_result.scalar_one_or_none()

        # Get supplier name for notification message
        supplier_name = "Unknown"
        if po:
            sup_result = await db.execute(select(Supplier.name).filter(Supplier.id == po.supplier_id))
            supplier_name = sup_result.scalar_one_or_none() or "Unknown"

        # Notify managers that goods were received
        from app.models.user import UserRole as UR
        target_users = await notification_service._get_users_by_roles([UR.MANAGER.value, UR.ADMIN.value])
        total_received = sum(item.quantity_received for item in request.items)
        for user in target_users:
            await notification_service.create_notification(
                user_id=user.id,
                notification_type=NotificationType.SYSTEM.value,
                title="Goods Received",
                message=f"GRN processed for PO from {supplier_name}. {len(request.items)} item(s), {total_received} units received.",
                metadata={
                    "entity_type": "grn",
                    "entity_id": str(grn.id),
                    "po_id": str(po_id),
                    "supplier_name": supplier_name,
                },
            )

        # Discrepancy alert: if any item received significantly less than ordered
        if po and po.items:
            po_items_map = {str(pi.id): pi for pi in po.items}
            discrepancies = []
            for req_item in request.items:
                po_item = po_items_map.get(str(req_item.po_item_id))
                if po_item:
                    ordered = float(po_item.quantity_ordered)
                    already_received = float(po_item.quantity_received)
                    remaining = ordered - already_received
                    received_now = float(req_item.quantity_received)
                    # Flag if received is less than 80% of remaining expected
                    if remaining > 0 and received_now < remaining * 0.8 and (remaining - received_now) > 1:
                        discrepancies.append(f"{po_item.spare_part_id}: received {received_now}/{remaining} expected")

            if discrepancies:
                for user in target_users:
                    await notification_service.create_notification(
                        user_id=user.id,
                        notification_type=NotificationType.SYSTEM.value,
                        title="GRN Quantity Discrepancy",
                        message=f"Goods from {supplier_name} received with quantity discrepancies. {len(discrepancies)} item(s) received significantly less than ordered.",
                        metadata={
                            "entity_type": "grn_discrepancy",
                            "entity_id": str(grn.id),
                            "po_id": str(po_id),
                            "discrepancies": discrepancies[:5],
                        },
                    )

        await db.commit()
        await db.refresh(grn)
        return GRNResponse.model_validate(grn)
    except PurchaseOrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )
    except InvalidPOStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except InvalidGRNQuantityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{po_id}/cancel",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a purchase order",
    description="Cancel a purchase order. Requires a reason for non-draft POs. Manager or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid PO state or missing reason"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Purchase order not found"},
    },
)
async def cancel_purchase_order(
    po_id: UUID,
    request: PurchaseOrderCancel,
    db: DbSession,
    current_user: User = Depends(
        require_permission("purchasing")
    ),
) -> PurchaseOrderResponse:
    """Cancel a purchase order.

    Requirements:
    - 9.7: Cancelling an ordered/partially_received PO requires reason and Manager/Admin
    """
    service = _get_purchase_service(db, current_user.id)

    try:
        po = await service.cancel_po(
            po_id=po_id,
            cancelled_by=current_user.id,
            reason=request.reason,
        )
        await db.commit()
        await db.refresh(po)
        return PurchaseOrderResponse.model_validate(po)
    except PurchaseOrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )
    except InvalidPOStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except CancellationReasonRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
