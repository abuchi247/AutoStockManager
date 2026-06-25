"""Sales router for sales transaction endpoints.

Provides the following endpoints:
- GET    /api/v1/sales              - List sales (paginated, filterable by status)
- POST   /api/v1/sales              - Create a sale in DRAFT status
- GET    /api/v1/sales/{id}         - Get sale by ID
- POST   /api/v1/sales/{id}/confirm - Confirm a sale (validate stock, consume FIFO)
- POST   /api/v1/sales/{id}/return  - Process a sales return (Manager, Admin)

Satisfies Requirements: 5.1, 5.3, 5.4
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.sale import Sale, SaleStatus, PaymentType
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.sale import (
    SaleCreate,
    SaleListResponse,
    SaleResponse,
    SaleReturnRequest,
)
from app.services.sales_service import (
    InsufficientStockError,
    InvalidSaleStatusError,
    SaleHasNoItemsError,
    SaleNotFoundError,
    SalesService,
)
from app.models.sale import SaleItem

router = APIRouter(prefix="/api/v1/sales", tags=["Sales"])


def _get_sales_service(db: AsyncSession, user_id: UUID) -> SalesService:
    """Create a SalesService instance."""
    return SalesService(db=db, user_id=user_id)


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=SaleListResponse,
    status_code=status.HTTP_200_OK,
    summary="List sales",
    description="Retrieve a paginated list of sales, optionally filtered by status. Accessible by Salesperson, Manager, and Admin.",
)
async def list_sales(
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by sale status (DRAFT, CONFIRMED, RETURNED, CANCELLED)",
    ),
) -> SaleListResponse:
    """List all sales with optional status filtering and pagination.

    Accessible by Salesperson, Manager, and Admin roles.
    """
    # Count query
    count_stmt = select(func.count()).select_from(Sale)
    if status_filter:
        count_stmt = count_stmt.filter(Sale.status == status_filter)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Data query
    offset = (page - 1) * page_size
    data_stmt = select(Sale).order_by(Sale.created_at.desc())
    if status_filter:
        data_stmt = data_stmt.filter(Sale.status == status_filter)
    data_stmt = data_stmt.offset(offset).limit(page_size)

    result = await db.execute(data_stmt)
    sales = list(result.scalars().all())

    return SaleListResponse(
        data=[SaleResponse.model_validate(s) for s in sales],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "",
    response_model=SaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a sale",
    description="Create a new sale in DRAFT status. Salesperson, Manager, or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    },
)
async def create_sale(
    request: SaleCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SaleResponse:
    """Create a new sale in DRAFT status.

    Requirements:
    - 5.1: Create a sale with customer, location, line items, payment type
    """
    service = _get_sales_service(db, current_user.id)

    # Prepare items for the service
    items = None
    if request.items:
        items = [
            {
                "spare_part_id": item.spare_part_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_amount": item.discount_amount,
            }
            for item in request.items
        ]

    sale = await service.create_sale(
        customer_id=request.customer_id,
        location_id=request.location_id,
        payment_type=PaymentType(request.payment_type),
        items=items,
    )
    await db.commit()
    await db.refresh(sale)
    return SaleResponse.model_validate(sale)


@router.get(
    "/{sale_id}",
    response_model=SaleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get sale by ID",
    description="Retrieve a single sale by its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "Sale not found"},
    },
)
async def get_sale(
    sale_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SaleResponse:
    """Get a single sale by its ID.

    Accessible by Salesperson, Manager, and Admin roles.
    Includes returned_quantity per item from the movement ledger.
    """
    from sqlalchemy.orm import selectinload
    from sqlalchemy import func as sa_func
    from app.models.inventory_movement_ledger import InventoryMovementLedger, MovementType

    stmt = (
        select(Sale)
        .filter_by(id=sale_id)
        .options(selectinload(Sale.items).selectinload(SaleItem.spare_part))
    )
    result = await db.execute(stmt)
    sale = result.scalar_one_or_none()

    if sale is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )

    # Query returned quantities per spare_part_id from the ledger
    return_stmt = (
        select(
            InventoryMovementLedger.spare_part_id,
            sa_func.sum(InventoryMovementLedger.quantity_change).label("total_returned"),
        )
        .filter(
            InventoryMovementLedger.reference_id == sale_id,
            InventoryMovementLedger.reference_type == "sale",
            InventoryMovementLedger.movement_type == MovementType.RETURN.value,
        )
        .group_by(InventoryMovementLedger.spare_part_id)
    )
    return_result = await db.execute(return_stmt)
    returned_map = {row.spare_part_id: row.total_returned for row in return_result}

    # Build response with returned_quantity
    from app.schemas.sale import SaleItemResponse, SaleResponse as SR
    items_response = []
    for item in sale.items:
        item_resp = SaleItemResponse.model_validate(item)
        item_resp.returned_quantity = returned_map.get(item.spare_part_id, 0)
        items_response.append(item_resp)

    resp = SaleResponse.model_validate(sale)
    resp.items = items_response
    return resp


@router.put(
    "/{sale_id}",
    response_model=SaleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a draft sale",
    description="Update a sale that is still in DRAFT status. Allows changing customer, payment type, and line items.",
    responses={
        400: {"model": ErrorResponse, "description": "Sale is not in DRAFT status"},
        404: {"model": ErrorResponse, "description": "Sale not found"},
    },
)
async def update_sale(
    sale_id: UUID,
    request: SaleCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SaleResponse:
    """Update a draft sale's customer, payment type, and line items.

    Only DRAFT sales can be edited. Once confirmed, a sale is immutable.
    """
    from decimal import Decimal

    stmt = select(Sale).filter_by(id=sale_id)
    result = await db.execute(stmt)
    sale = result.scalar_one_or_none()

    if sale is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found",
        )

    if sale.status != SaleStatus.DRAFT.value and sale.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft sales can be edited",
        )

    # Update basic fields
    if request.customer_id is not None:
        sale.customer_id = request.customer_id
    sale.location_id = request.location_id
    sale.payment_type = request.payment_type

    # Remove existing line items
    existing_items_stmt = select(SaleItem).filter_by(sale_id=sale_id)
    existing_result = await db.execute(existing_items_stmt)
    for item in existing_result.scalars().all():
        await db.delete(item)

    # Add new line items
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    if request.items:
        for item_data in request.items:
            line_total = Decimal(str(item_data.quantity)) * Decimal(str(item_data.unit_price)) - Decimal(str(item_data.discount_amount or 0))
            new_item = SaleItem(
                sale_id=sale_id,
                spare_part_id=item_data.spare_part_id,
                quantity=item_data.quantity,
                unit_price=Decimal(str(item_data.unit_price)),
                discount_amount=Decimal(str(item_data.discount_amount or 0)),
                line_total=line_total,
            )
            db.add(new_item)
            subtotal += line_total
            discount_total += Decimal(str(item_data.discount_amount or 0))

    sale.subtotal = subtotal
    sale.discount_total = discount_total
    sale.total_amount = subtotal
    sale.updated_by = str(current_user.id)

    await db.commit()

    # Re-fetch with eager loading for the response
    from sqlalchemy.orm import selectinload
    stmt = (
        select(Sale)
        .filter_by(id=sale_id)
        .options(selectinload(Sale.items).selectinload(SaleItem.spare_part))
    )
    result = await db.execute(stmt)
    sale = result.scalar_one()

    return SaleResponse.model_validate(sale)


@router.post(
    "/{sale_id}/confirm",
    response_model=SaleResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm a sale",
    description="Confirm a DRAFT sale: validates stock, consumes FIFO layers, records ledger entries. Salesperson, Manager, or Admin.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid state or no items"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Sale not found"},
        409: {"model": ErrorResponse, "description": "Insufficient stock"},
    },
)
async def confirm_sale(
    sale_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SaleResponse:
    """Confirm a sale, deducting stock and calculating COGS.

    Requirements:
    - 5.2: Reduce stock at selling location via ledger entries
    - 5.3: Cash sale marked as fully paid
    - 5.6: Reject if quantity exceeds available stock
    - 5.9: Pessimistic lock on stock records
    - 5.10: Stock validation and deduction in same transaction
    """
    service = _get_sales_service(db, current_user.id)

    try:
        sale = await service.confirm_sale(sale_id=sale_id)
        await db.commit()
        await db.refresh(sale)
        return SaleResponse.model_validate(sale)
    except SaleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidSaleStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except SaleHasNoItemsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except InsufficientStockError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/{sale_id}/return",
    response_model=SaleResponse,
    status_code=status.HTTP_200_OK,
    summary="Process a sales return",
    description="Process a return for a confirmed sale. Creates new cost layers and reverses inventory. Manager or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid sale state"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Sale not found"},
    },
)
async def return_sale(
    sale_id: UUID,
    db: DbSession,
    request: Optional[SaleReturnRequest] = None,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SaleResponse:
    """Process a sales return.

    Requirements:
    - 5.8: Support sales returns reversing inventory and financial entries
    - 5.12: Return creates new cost layer using original sale item's unit cost
    - 5.13: Cost layer timestamp = return processing date
    - 5.14: Never modify or re-open previously consumed/closed cost layers
    """
    service = _get_sales_service(db, current_user.id)

    # Build return_items list for the service
    return_items = None
    if request and request.items:
        return_items = [
            {
                "sale_item_id": item.sale_item_id,
                "quantity": item.quantity,
            }
            for item in request.items
        ]

    try:
        sale = await service.return_sale(
            sale_id=sale_id,
            returned_by=current_user.id,
            return_items=return_items,
        )
        await db.commit()
        await db.refresh(sale)
        return SaleResponse.model_validate(sale)
    except SaleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidSaleStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
