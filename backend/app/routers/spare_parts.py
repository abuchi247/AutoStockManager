"""Spare parts inventory router with CRUD and search endpoints.

Provides the following endpoints:
- GET    /api/v1/spare-parts          - List all spare parts (paginated)
- POST   /api/v1/spare-parts          - Create a new spare part
- GET    /api/v1/spare-parts/search   - Search spare parts with filters
- GET    /api/v1/spare-parts/{id}     - Get spare part by ID
- PUT    /api/v1/spare-parts/{id}     - Update a spare part
- DELETE /api/v1/spare-parts/{id}     - Soft-delete a spare part

Satisfies Requirements: 3.1, 3.2, 3.4, 3.5
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.stock_status_cache import StockStatusCache
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.spare_part import (
    SparePartCreate,
    SparePartListResponse,
    SparePartResponse,
    SparePartUpdate,
)
from app.services.inventory_service import (
    CategoryNotFoundError,
    DuplicateBarcodeError,
    DuplicatePartNumberError,
    InventoryService,
    SparePartNotFoundError,
)

router = APIRouter(prefix="/api/v1/spare-parts", tags=["Spare Parts"])


def _get_inventory_service(db) -> InventoryService:
    """Create an InventoryService instance."""
    return InventoryService(db=db)


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=SparePartListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all spare parts",
    description="Retrieve a paginated list of all active spare parts.",
)
async def list_spare_parts(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    location_id: Optional[str] = Query(default=None, description="Filter by location ID"),
    search: Optional[str] = Query(default=None, description="Search by name, part number, or barcode"),
    brand: Optional[str] = Query(default=None, description="Filter by brand"),
    category_id: Optional[str] = Query(default=None, description="Filter by category ID"),
) -> SparePartListResponse:
    """List all active spare parts with pagination and filters.

    Accessible by all authenticated users.
    """
    from uuid import UUID as UUIDType
    from app.models.spare_part import SparePart as SP

    # Build base query with filters
    base_filter = [SP.deleted_at.is_(None)]

    if search:
        search_term = f"%{search}%"
        from sqlalchemy import or_
        base_filter.append(
            or_(
                SP.name.ilike(search_term),
                SP.part_number.ilike(search_term),
                SP.barcode.ilike(search_term),
            )
        )

    if brand:
        base_filter.append(SP.brand.ilike(f"%{brand}%"))

    if category_id:
        cat_uuid = UUIDType(category_id)
        base_filter.append(SP.category_id == cat_uuid)

    if location_id:
        # Join with stock cache to filter by location
        loc_uuid = UUIDType(location_id)

        count_stmt = (
            select(func.count(SP.id.distinct()))
            .join(StockStatusCache, StockStatusCache.spare_part_id == SP.id)
            .filter(
                *base_filter,
                StockStatusCache.location_id == loc_uuid,
                StockStatusCache.current_quantity > 0,
            )
        )
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(SP)
            .join(StockStatusCache, StockStatusCache.spare_part_id == SP.id)
            .filter(
                *base_filter,
                StockStatusCache.location_id == loc_uuid,
                StockStatusCache.current_quantity > 0,
            )
            .order_by(SP.name.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        spare_parts = list(result.scalars().all())

        # Get stock at this specific location
        stock_map = {}
        part_ids = [sp.id for sp in spare_parts]
        if part_ids:
            stock_stmt = (
                select(
                    StockStatusCache.spare_part_id,
                    StockStatusCache.current_quantity,
                )
                .filter(
                    StockStatusCache.spare_part_id.in_(part_ids),
                    StockStatusCache.location_id == loc_uuid,
                )
            )
            stock_result = await db.execute(stock_stmt)
            stock_map = {row.spare_part_id: row.current_quantity for row in stock_result}
    else:
        # No location filter — standard list with optional search/brand/category
        count_stmt = select(func.count(SP.id)).filter(*base_filter)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(SP)
            .filter(*base_filter)
            .order_by(SP.name.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        spare_parts = list(result.scalars().all())

        # Get total stock for each part from cache
        part_ids = [sp.id for sp in spare_parts]
        stock_map: dict = {}
        if part_ids:
            stock_stmt = (
                select(
                    StockStatusCache.spare_part_id,
                    func.sum(StockStatusCache.current_quantity).label("total_stock"),
                )
                .filter(StockStatusCache.spare_part_id.in_(part_ids))
                .group_by(StockStatusCache.spare_part_id)
            )
            stock_result = await db.execute(stock_stmt)
            stock_map = {row.spare_part_id: row.total_stock for row in stock_result}

    data = []
    for sp in spare_parts:
        resp = SparePartResponse.model_validate(sp)
        resp.total_stock = stock_map.get(sp.id)
        data.append(resp)

    return SparePartListResponse(
        data=data,
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.get(
    "/next-part-number",
    status_code=status.HTTP_200_OK,
    summary="Get next available part number",
    description="Generates the next sequential part number in the format ASM-XXXXX.",
)
async def get_next_part_number(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Generate the next available part number."""
    from app.models.spare_part import SparePart as SP

    # Find the highest existing ASM-XXXXX number
    stmt = (
        select(func.count(SP.id))
        .filter(SP.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    count = (result.scalar() or 0) + 1

    # Generate next number with zero-padding
    next_number = f"ASM-{count:05d}"

    # Make sure it doesn't already exist
    while True:
        check_stmt = select(func.count(SP.id)).filter(SP.part_number == next_number)
        check_result = await db.execute(check_stmt)
        if (check_result.scalar() or 0) == 0:
            break
        count += 1
        next_number = f"ASM-{count:05d}"

    return {"part_number": next_number}


@router.post(
    "",
    response_model=SparePartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new spare part",
    description="Create a new spare part record. Storekeeper, Manager, or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        409: {"model": ErrorResponse, "description": "Duplicate part_number or barcode"},
    },
)
async def create_spare_part(
    request: SparePartCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SparePartResponse:
    """Create a new spare part.

    Requirements:
    - 3.1: Store spare part with all required attributes
    - 3.2: Enforce unique constraints on part_number and barcode
    - 3.4: Support hierarchical categorization
    """
    service = _get_inventory_service(db)

    try:
        spare_part = await service.create_spare_part(
            data=request,
            created_by=str(current_user.id),
        )
        await db.commit()
        await db.refresh(spare_part)
        return SparePartResponse.model_validate(spare_part)
    except DuplicatePartNumberError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )
    except DuplicateBarcodeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )
    except CategoryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.get(
    "/search",
    response_model=SparePartListResponse,
    status_code=status.HTTP_200_OK,
    summary="Search spare parts",
    description="Search spare parts by part_number, barcode, name, brand, category, or vehicle compatibility.",
)
async def search_spare_parts(
    db: DbSession,
    current_user: CurrentUser,
    q: Optional[str] = Query(
        default=None,
        description="General search term (matches part_number, barcode, name, brand)",
    ),
    part_number: Optional[str] = Query(
        default=None, description="Filter by partial part number"
    ),
    barcode: Optional[str] = Query(
        default=None, description="Filter by exact barcode"
    ),
    name: Optional[str] = Query(
        default=None, description="Filter by partial name match"
    ),
    brand: Optional[str] = Query(
        default=None, description="Filter by brand name"
    ),
    category_id: Optional[UUID] = Query(
        default=None, description="Filter by category UUID"
    ),
    vehicle_compatibility: Optional[str] = Query(
        default=None, description="Filter by vehicle compatibility text"
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> SparePartListResponse:
    """Search spare parts with multiple filter criteria.

    Requirement 3.5: Support search by part_number, barcode, name, brand,
    category, and vehicle_compatibility.

    Accessible by all authenticated users.
    """
    service = _get_inventory_service(db)
    spare_parts, total = await service.search_spare_parts(
        q=q,
        part_number=part_number,
        barcode=barcode,
        name=name,
        brand=brand,
        category_id=category_id,
        vehicle_compatibility=vehicle_compatibility,
        page=page,
        page_size=page_size,
    )

    return SparePartListResponse(
        data=[SparePartResponse.model_validate(sp) for sp in spare_parts],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.get(
    "/{spare_part_id}",
    response_model=SparePartResponse,
    status_code=status.HTTP_200_OK,
    summary="Get spare part by ID",
    description="Retrieve a single spare part by its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "Spare part not found"},
    },
)
async def get_spare_part(
    spare_part_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> SparePartResponse:
    """Get a single spare part by ID.

    Accessible by all authenticated users.
    """
    service = _get_inventory_service(db)

    try:
        spare_part = await service.get_spare_part(spare_part_id)
        resp = SparePartResponse.model_validate(spare_part)

        # Get total stock from cache
        stock_stmt = (
            select(func.sum(StockStatusCache.current_quantity).label("total_stock"))
            .filter(StockStatusCache.spare_part_id == spare_part_id)
        )
        stock_result = await db.execute(stock_stmt)
        resp.total_stock = stock_result.scalar()

        return resp
    except SparePartNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spare part not found",
        )


@router.put(
    "/{spare_part_id}",
    response_model=SparePartResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a spare part",
    description="Update an existing spare part's attributes. Storekeeper, Manager, or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Spare part not found"},
        409: {"model": ErrorResponse, "description": "Duplicate part_number or barcode"},
    },
)
async def update_spare_part(
    spare_part_id: UUID,
    request: SparePartUpdate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SparePartResponse:
    """Update a spare part's attributes (partial update).

    Requirements:
    - 3.2: Enforce unique constraints on part_number and barcode
    """
    service = _get_inventory_service(db)

    try:
        spare_part = await service.update_spare_part(
            spare_part_id=spare_part_id,
            data=request,
            updated_by=str(current_user.id),
        )
        await db.commit()
        await db.refresh(spare_part)
        return SparePartResponse.model_validate(spare_part)
    except SparePartNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spare part not found",
        )
    except DuplicatePartNumberError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )
    except DuplicateBarcodeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        )
    except CategoryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )


@router.delete(
    "/{spare_part_id}",
    response_model=SparePartResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a spare part",
    description="Soft-delete a spare part. Manager or Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Spare part not found"},
    },
)
async def delete_spare_part(
    spare_part_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SparePartResponse:
    """Soft-delete a spare part.

    Requirement 1.2: Perform soft-delete by setting deleted_at timestamp.
    Only Managers and Admins can delete spare parts.
    """
    service = _get_inventory_service(db)

    try:
        spare_part = await service.delete_spare_part(
            spare_part_id=spare_part_id,
            deleted_by=str(current_user.id),
        )
        await db.commit()
        return SparePartResponse.model_validate(spare_part)
    except SparePartNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Spare part not found",
        )
