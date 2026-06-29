"""Stock query router for reading stock levels and making adjustments.

Provides the following endpoints:
- GET  /api/v1/stock/locations/{id}            - Get stock at a specific location
- POST /api/v1/stock/adjust                    - Make a manual stock adjustment
- GET  /api/v1/stock/movements/{spare_part_id} - Get movement history for a spare part
- GET  /api/v1/stock/cost-layers/{spare_part_id} - Get FIFO cost layers for a spare part

Reads from Stock_Status_Cache for performant stock queries rather than
computing quantities from the full movement ledger.

Satisfies Requirements: 18.1, 18.3, 18.8
"""

import uuid as uuid_mod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.user import User, UserRole
from app.models.inventory_movement_ledger import InventoryMovementLedger, MovementType, ReferenceType
from app.models.cost_layer import CostLayer
from app.models.stock_status_cache import StockStatusCache
from app.models.spare_part import SparePart
from app.models.location import Location
from app.schemas.stock import StockItemResponse, StockLocationResponse
from app.services.stock_service import LocationNotFoundError, StockService

router = APIRouter(prefix="/api/v1/stock", tags=["Stock"])


class StockAdjustmentRequest(BaseModel):
    """Request body for manual stock adjustment."""
    spare_part_id: UUID = Field(..., description="The spare part to adjust")
    location_id: UUID = Field(..., description="The location where stock is being adjusted")
    quantity: int = Field(..., description="Quantity to add (positive) or remove (negative)")
    reason: str = Field(default="Manual adjustment", max_length=500, description="Reason for the adjustment")


class StockAdjustmentResponse(BaseModel):
    """Response for a stock adjustment."""
    spare_part_id: UUID
    location_id: UUID
    quantity_change: int
    new_quantity: float
    reason: str
    movement_id: UUID


@router.post(
    "/adjust",
    response_model=StockAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Make a stock adjustment",
    description="Manually adjust stock for a spare part at a specific location. "
    "Use positive quantities to add stock, negative to remove. Admin or Storekeeper only.",
    responses={
        404: {"description": "Spare part or location not found"},
        400: {"description": "Insufficient stock for negative adjustment"},
    },
)
async def adjust_stock(
    request: StockAdjustmentRequest,
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.STOREKEEPER, UserRole.MANAGER)),
) -> StockAdjustmentResponse:
    """Make a manual stock adjustment.

    Creates a ledger entry and updates the stock status cache.
    Used for initial stock setup, corrections, or write-offs.
    """
    # Validate spare part exists
    part_result = await db.execute(
        select(SparePart).filter_by(id=request.spare_part_id, deleted_at=None)
    )
    part = part_result.scalar_one_or_none()
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spare part not found",
        )

    # Validate location exists
    location_result = await db.execute(
        select(Location).filter_by(id=request.location_id, deleted_at=None)
    )
    location = location_result.scalar_one_or_none()
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    # Get or create stock cache entry
    cache_result = await db.execute(
        select(StockStatusCache).filter_by(
            spare_part_id=request.spare_part_id,
            location_id=request.location_id,
        )
    )
    cache = cache_result.scalar_one_or_none()

    current_qty = float(cache.current_quantity) if cache else 0.0

    # Validate negative adjustments don't go below zero
    if request.quantity < 0 and (current_qty + request.quantity) < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock. Current: {current_qty}, adjustment: {request.quantity}",
        )

    # Create ledger entry
    movement_id = uuid_mod.uuid4()
    now = datetime.now(timezone.utc)
    ledger_entry = InventoryMovementLedger(
        id=movement_id,
        spare_part_id=request.spare_part_id,
        location_id=request.location_id,
        quantity_change=Decimal(str(request.quantity)),
        movement_type=MovementType.ADJUSTMENT.value,
        reference_type="adjustment",
        reference_id=movement_id,
        unit_cost=Decimal(str(part.cost_price)) if part.cost_price else Decimal("0"),
        created_by=current_user.id,
        created_at=now,
    )
    db.add(ledger_entry)

    # Create cost layer for positive adjustments (needed for FIFO sales)
    if request.quantity > 0:
        cost_layer = CostLayer(
            id=uuid_mod.uuid4(),
            spare_part_id=request.spare_part_id,
            location_id=request.location_id,
            unit_cost=Decimal(str(part.cost_price)) if part.cost_price else Decimal("0"),
            original_quantity=Decimal(str(request.quantity)),
            remaining_quantity=Decimal(str(request.quantity)),
            source_type="adjustment",
            source_reference_id=movement_id,
            created_at=now,
        )
        db.add(cost_layer)

    # Update stock cache
    new_qty = current_qty + request.quantity
    if cache:
        cache.current_quantity = Decimal(str(new_qty))
        cache.updated_at = now
    else:
        new_cache = StockStatusCache(
            id=uuid_mod.uuid4(),
            spare_part_id=request.spare_part_id,
            location_id=request.location_id,
            current_quantity=Decimal(str(new_qty)),
            updated_at=now,
        )
        db.add(new_cache)

    await db.commit()

    return StockAdjustmentResponse(
        spare_part_id=request.spare_part_id,
        location_id=request.location_id,
        quantity_change=request.quantity,
        new_quantity=new_qty,
        reason=request.reason,
        movement_id=movement_id,
    )


@router.get(
    "/locations/{location_id}",
    response_model=StockLocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get stock at a location",
    description="Retrieves current stock quantities for all spare parts at a given location. "
    "Reads from the Stock_Status_Cache for fast performance.",
    responses={
        404: {"description": "Location not found"},
    },
)
async def get_stock_at_location(
    location_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
) -> StockLocationResponse:
    """Get stock quantities at a specific location.

    Returns paginated stock cache entries for the specified location,
    including spare part names and part numbers for display convenience.

    Requirements:
    - 18.1: Stock_Status_Cache tracks current_quantity per part per location
    - 18.3: Read from Stock_Status_Cache for stock quantity queries
    """
    stock_service = StockService(db=db)

    try:
        result = await stock_service.get_stock_at_location(
            location_id=location_id,
            page=page,
            page_size=page_size,
        )
    except LocationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with id '{location_id}' not found",
        )

    # Convert items to response models
    stock_items = [StockItemResponse(**item) for item in result["data"]]

    return StockLocationResponse(
        location_id=result["location_id"],
        location_name=result["location_name"],
        data=stock_items,
        meta=result["meta"],
    )


# =============================================================================
# Response Models for Movement History and Cost Layers
# =============================================================================


class MovementHistoryItem(BaseModel):
    """Single movement ledger entry."""
    id: UUID
    location_id: UUID
    location_name: Optional[str] = None
    quantity_change: float
    movement_type: str
    reference_type: str
    reference_id: UUID
    created_by: UUID
    created_by_username: Optional[str] = None
    created_at: datetime


class MovementHistoryResponse(BaseModel):
    """Paginated response for movement history."""
    data: list[MovementHistoryItem]
    meta: dict[str, Any]


class CostLayerItem(BaseModel):
    """Single cost layer entry."""
    id: UUID
    location_id: UUID
    location_name: Optional[str] = None
    unit_cost: float
    original_quantity: float
    remaining_quantity: float
    source_type: str
    created_at: datetime


class CostLayerResponse(BaseModel):
    """Paginated response for cost layers."""
    data: list[CostLayerItem]
    meta: dict[str, Any]


# =============================================================================
# Movement History Endpoint
# =============================================================================


@router.get(
    "/movements/{spare_part_id}",
    response_model=MovementHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get movement history for a spare part",
    description="Returns paginated stock movement history from the inventory movement ledger.",
    responses={
        404: {"description": "Spare part not found"},
    },
)
async def get_movement_history(
    spare_part_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> MovementHistoryResponse:
    """Get all stock movements for a specific spare part.

    Returns movements ordered by created_at descending (most recent first),
    with location names resolved for display.
    """
    # Validate spare part exists
    part_result = await db.execute(
        select(SparePart).filter_by(id=spare_part_id, deleted_at=None)
    )
    part = part_result.scalar_one_or_none()
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spare part not found",
        )

    # Count total movements
    count_stmt = (
        select(func.count())
        .select_from(InventoryMovementLedger)
        .where(InventoryMovementLedger.spare_part_id == spare_part_id)
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch paginated movements with location names
    offset = (page - 1) * page_size
    stmt = (
        select(InventoryMovementLedger, Location.name.label("location_name"), User.username.label("created_by_username"))
        .outerjoin(Location, InventoryMovementLedger.location_id == Location.id)
        .outerjoin(User, InventoryMovementLedger.created_by == User.id)
        .where(InventoryMovementLedger.spare_part_id == spare_part_id)
        .order_by(InventoryMovementLedger.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = [
        MovementHistoryItem(
            id=row.InventoryMovementLedger.id,
            location_id=row.InventoryMovementLedger.location_id,
            location_name=row.location_name,
            quantity_change=float(row.InventoryMovementLedger.quantity_change),
            movement_type=row.InventoryMovementLedger.movement_type,
            reference_type=row.InventoryMovementLedger.reference_type,
            reference_id=row.InventoryMovementLedger.reference_id,
            created_by=row.InventoryMovementLedger.created_by,
            created_by_username=row.created_by_username,
            created_at=row.InventoryMovementLedger.created_at,
        )
        for row in rows
    ]

    return MovementHistoryResponse(
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


# =============================================================================
# Stock By Location Endpoint (per spare part)
# =============================================================================


class StockByLocationItem(BaseModel):
    """Stock at a single location for a spare part."""
    location_id: UUID
    location_name: Optional[str] = None
    current_quantity: float


class StockByLocationResponse(BaseModel):
    """All locations and quantities for a spare part."""
    spare_part_id: UUID
    data: list[StockByLocationItem]


@router.get(
    "/by-part/{spare_part_id}",
    response_model=StockByLocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get stock breakdown by location for a spare part",
    description="Returns all locations where this spare part has stock, with quantities.",
)
async def get_stock_by_part(
    spare_part_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> StockByLocationResponse:
    """Get stock quantity at each location for a specific spare part."""
    stmt = (
        select(StockStatusCache, Location.name.label("location_name"))
        .outerjoin(Location, StockStatusCache.location_id == Location.id)
        .where(StockStatusCache.spare_part_id == spare_part_id)
        .where(StockStatusCache.current_quantity > 0)
        .order_by(Location.name.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = [
        StockByLocationItem(
            location_id=row.StockStatusCache.location_id,
            location_name=row.location_name,
            current_quantity=float(row.StockStatusCache.current_quantity),
        )
        for row in rows
    ]

    return StockByLocationResponse(spare_part_id=spare_part_id, data=items)


# =============================================================================
# Cost Layers Endpoint
# =============================================================================


@router.get(
    "/cost-layers/{spare_part_id}",
    response_model=CostLayerResponse,
    status_code=status.HTTP_200_OK,
    summary="Get FIFO cost layers for a spare part",
    description="Returns active cost layers (remaining_quantity > 0) for a spare part.",
    responses={
        404: {"description": "Spare part not found"},
    },
)
async def get_cost_layers(
    spare_part_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> CostLayerResponse:
    """Get active FIFO cost layers for a specific spare part.

    Returns cost layers where remaining_quantity > 0, ordered by created_at
    ascending (oldest first, per FIFO), with location names resolved.
    """
    # Validate spare part exists
    part_result = await db.execute(
        select(SparePart).filter_by(id=spare_part_id, deleted_at=None)
    )
    part = part_result.scalar_one_or_none()
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spare part not found",
        )

    # Count total active cost layers
    count_stmt = (
        select(func.count())
        .select_from(CostLayer)
        .where(CostLayer.spare_part_id == spare_part_id)
        .where(CostLayer.remaining_quantity > 0)
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch paginated cost layers with location names
    offset = (page - 1) * page_size
    stmt = (
        select(CostLayer, Location.name.label("location_name"))
        .outerjoin(Location, CostLayer.location_id == Location.id)
        .where(CostLayer.spare_part_id == spare_part_id)
        .where(CostLayer.remaining_quantity > 0)
        .order_by(CostLayer.created_at.asc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = [
        CostLayerItem(
            id=row.CostLayer.id,
            location_id=row.CostLayer.location_id,
            location_name=row.location_name,
            unit_cost=float(row.CostLayer.unit_cost),
            original_quantity=float(row.CostLayer.original_quantity),
            remaining_quantity=float(row.CostLayer.remaining_quantity),
            source_type=row.CostLayer.source_type,
            created_at=row.CostLayer.created_at,
        )
        for row in rows
    ]

    return CostLayerResponse(
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )
