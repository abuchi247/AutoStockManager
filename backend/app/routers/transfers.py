"""Transfer router for inter-location stock movement endpoints.

Provides the following endpoints:
- GET    /api/v1/transfers              - List transfers (paginated, filterable by status)
- POST   /api/v1/transfers              - Create a transfer request
- POST   /api/v1/transfers/{id}/approve - Approve a transfer (Manager, Admin)
- POST   /api/v1/transfers/{id}/receive - Receive a transfer at destination
- POST   /api/v1/transfers/{id}/cancel  - Cancel a transfer (Manager, Admin)

Satisfies Requirements: 4.2, 4.4, 4.5, 4.6
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.transfer import Transfer, TransferStatus
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.transfer import (
    TransferCancel,
    TransferCreate,
    TransferListResponse,
    TransferResponse,
)
from app.services.transfer_service import (
    InsufficientStockError,
    InvalidTransferError,
    InvalidTransferStateError,
    InvalidTransferStatusError,
    LocationNotFoundError,
    SparePartNotFoundError,
    TransferNotFoundError,
    TransferService,
)

router = APIRouter(prefix="/api/v1/transfers", tags=["Transfers"])


def _get_transfer_service(db: AsyncSession) -> TransferService:
    """Create a TransferService instance."""
    return TransferService(db=db)


async def _enrich_transfers(db: AsyncSession, transfers: list[Transfer]) -> list[TransferResponse]:
    """Enrich transfer records with spare part and location names."""
    from app.models.spare_part import SparePart
    from app.models.location import Location

    if not transfers:
        return []

    # Batch-load part names
    part_ids = list({t.spare_part_id for t in transfers})
    part_stmt = select(SparePart.id, SparePart.name, SparePart.part_number).filter(SparePart.id.in_(part_ids))
    part_result = await db.execute(part_stmt)
    part_map = {row.id: (row.name, row.part_number) for row in part_result.all()}

    # Batch-load location names
    loc_ids = list({t.source_location_id for t in transfers} | {t.destination_location_id for t in transfers})
    loc_stmt = select(Location.id, Location.name).filter(Location.id.in_(loc_ids))
    loc_result = await db.execute(loc_stmt)
    loc_map = {row.id: row.name for row in loc_result.all()}

    # Build enriched responses
    enriched = []
    for t in transfers:
        resp = TransferResponse.model_validate(t)
        part_info = part_map.get(t.spare_part_id)
        resp.spare_part_name = part_info[0] if part_info else None
        resp.spare_part_number = part_info[1] if part_info else None
        resp.source_location_name = loc_map.get(t.source_location_id)
        resp.destination_location_name = loc_map.get(t.destination_location_id)
        enriched.append(resp)

    return enriched


async def _enrich_single_transfer(db: AsyncSession, transfer: Transfer) -> TransferResponse:
    """Enrich a single transfer with spare part and location names."""
    results = await _enrich_transfers(db, [transfer])
    return results[0]


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=TransferListResponse,
    status_code=status.HTTP_200_OK,
    summary="List transfers",
    description="Retrieve a paginated list of transfers, optionally filtered by status.",
)
async def list_transfers(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by transfer status (PENDING, APPROVED, IN_TRANSIT, RECEIVED, CANCELLED)",
    ),
) -> TransferListResponse:
    """List all transfers with optional status filtering and pagination.

    Accessible by all authenticated users.
    """
    # Count query
    count_stmt = select(func.count()).select_from(Transfer)
    if status_filter:
        count_stmt = count_stmt.filter(Transfer.status == status_filter)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Data query
    offset = (page - 1) * page_size
    data_stmt = select(Transfer).order_by(Transfer.created_at.desc())
    if status_filter:
        data_stmt = data_stmt.filter(Transfer.status == status_filter)
    data_stmt = data_stmt.offset(offset).limit(page_size)

    result = await db.execute(data_stmt)
    transfers = list(result.scalars().all())

    # Enrich transfers with part/location names
    enriched = await _enrich_transfers(db, transfers)

    return TransferListResponse(
        data=enriched,
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a transfer request",
    description="Create a new inter-location stock transfer request. Storekeeper, Manager, or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Spare part or location not found"},
    },
)
async def create_transfer(
    request: TransferCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> TransferResponse:
    """Create a new transfer request.

    Requirements:
    - 4.2: Transfer request specifying source, destination, spare part, quantity
    - 4.4: Initial state is 'PENDING'
    """
    service = _get_transfer_service(db)

    try:
        transfer = await service.create_transfer(
            spare_part_id=request.spare_part_id,
            source_location_id=request.source_location_id,
            destination_location_id=request.destination_location_id,
            quantity=request.quantity,
            requested_by=current_user.id,
        )
        await db.commit()
        await db.refresh(transfer)
        return await _enrich_single_transfer(db, transfer)
    except InvalidTransferError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except SparePartNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except LocationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InsufficientStockError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "/{transfer_id}",
    response_model=TransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transfer by ID",
    description="Retrieve a single transfer by its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "Transfer not found"},
    },
)
async def get_transfer(
    transfer_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> TransferResponse:
    """Get a single transfer by its ID.

    Accessible by all authenticated users.
    """
    service = _get_transfer_service(db)

    try:
        transfer = await service._get_transfer(transfer_id)
        return await _enrich_single_transfer(db, transfer)
    except TransferNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer not found",
        )


@router.post(
    "/{transfer_id}/approve",
    response_model=TransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve a transfer",
    description="Approve a pending transfer request. Deducts stock from source location. Manager or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid state"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Transfer not found"},
        409: {"model": ErrorResponse, "description": "Insufficient stock at source"},
    },
)
async def approve_transfer(
    transfer_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> TransferResponse:
    """Approve a pending transfer and deduct stock from source.

    Requirements:
    - 4.5: Deduct from source via ledger entries with FIFO consumption
    - 4.9: Reject if quantity exceeds available stock
    - 4.11: FIFO cost layer consumption at source
    """
    service = _get_transfer_service(db)

    try:
        transfer = await service.approve_transfer(
            transfer_id=transfer_id,
            approved_by=current_user.id,
        )
        await db.commit()
        await db.refresh(transfer)
        return await _enrich_single_transfer(db, transfer)
    except TransferNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidTransferStatusError as e:
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
    "/{transfer_id}/receive",
    response_model=TransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive a transfer at destination",
    description="Mark a transfer as received at the destination location. Storekeeper, Manager, or Admin.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid transfer state"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Transfer not found"},
    },
)
async def receive_transfer(
    transfer_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> TransferResponse:
    """Receive a transfer at the destination location.

    Requirements:
    - 4.6: Add to destination via ledger entries
    - 4.10: Create new cost layers at destination with source unit costs
    - 4.12: Consume from source layers, create new at destination
    """
    service = _get_transfer_service(db)

    try:
        transfer = await service.receive_transfer(
            transfer_id=transfer_id,
            received_by=current_user.id,
        )
        await db.commit()
        await db.refresh(transfer)
        return await _enrich_single_transfer(db, transfer)
    except TransferNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidTransferStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{transfer_id}/cancel",
    response_model=TransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a transfer",
    description="Cancel a pending or in-transit transfer. Manager or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid transfer state"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Transfer not found"},
    },
)
async def cancel_transfer(
    transfer_id: UUID,
    request: TransferCancel,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> TransferResponse:
    """Cancel a transfer that has not yet been received.

    Only pending or in-transit transfers can be cancelled.
    """
    service = _get_transfer_service(db)

    try:
        transfer = await service.cancel_transfer(
            transfer_id=transfer_id,
            cancelled_by=current_user.id,
            reason=request.reason,
        )
        await db.commit()
        await db.refresh(transfer)
        return await _enrich_single_transfer(db, transfer)
    except TransferNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidTransferStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except InvalidTransferStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
