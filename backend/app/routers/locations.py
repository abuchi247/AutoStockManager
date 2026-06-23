"""Location management router with CRUD endpoints.

Provides the following endpoints:
- GET    /api/v1/locations              - List all locations (paginated)
- POST   /api/v1/locations              - Create a new location (Admin, Manager)
- GET    /api/v1/locations/{id}         - Get location by ID
- PUT    /api/v1/locations/{id}         - Update a location (Admin, Manager)
- DELETE /api/v1/locations/{id}         - Soft-delete a location (Admin only)

Satisfies Requirement 4.1: Location management for warehouses and retail branches.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.location import Location
from app.models.user import User, UserRole
from app.models.base import SoftDeleteQuery
from app.schemas.auth import ErrorResponse
from app.schemas.location import (
    LocationCreate,
    LocationListResponse,
    LocationResponse,
    LocationUpdate,
)

router = APIRouter(prefix="/api/v1/locations", tags=["Locations"])


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=LocationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all locations",
    description="Retrieve a paginated list of all active locations.",
)
async def list_locations(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(
        default=None, description="Search by name or address"
    ),
) -> LocationListResponse:
    """List all active locations with pagination.

    Accessible by all authenticated users.
    """
    # Base query filtering out soft-deleted records
    base_query = SoftDeleteQuery.active(select(Location), Location)

    if search:
        search_filter = f"%{search}%"
        base_query = base_query.filter(
            (Location.name.ilike(search_filter))
            | (Location.address.ilike(search_filter))
        )

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Paginated results
    offset = (page - 1) * page_size
    stmt = base_query.order_by(Location.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    locations = result.scalars().all()

    return LocationListResponse(
        data=[LocationResponse.model_validate(loc) for loc in locations],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new location",
    description="Create a new location. Admin or Manager only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    },
)
async def create_location(
    request: LocationCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> LocationResponse:
    """Create a new location.

    Requirement 4.1: Support defining multiple storage locations.
    """
    location = Location(
        name=request.name,
        type=request.type,
        address=request.address or "",
        is_active=request.is_active,
        created_by=str(current_user.id),
    )

    db.add(location)
    await db.commit()
    await db.refresh(location)
    return LocationResponse.model_validate(location)


@router.get(
    "/{location_id}",
    response_model=LocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get location by ID",
    description="Retrieve a single location by its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "Location not found"},
    },
)
async def get_location(
    location_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> LocationResponse:
    """Get a single location by ID.

    Accessible by all authenticated users.
    """
    stmt = SoftDeleteQuery.active(
        select(Location).filter(Location.id == location_id), Location
    )
    result = await db.execute(stmt)
    location = result.scalar_one_or_none()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    return LocationResponse.model_validate(location)


@router.put(
    "/{location_id}",
    response_model=LocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a location",
    description="Update an existing location's attributes. Admin or Manager only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Location not found"},
    },
)
async def update_location(
    location_id: UUID,
    request: LocationUpdate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> LocationResponse:
    """Update a location's attributes (partial update)."""
    stmt = SoftDeleteQuery.active(
        select(Location).filter(Location.id == location_id), Location
    )
    result = await db.execute(stmt)
    location = result.scalar_one_or_none()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    # Apply only the fields that were provided
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(location, field, value)

    location.updated_by = str(current_user.id)

    await db.commit()
    await db.refresh(location)
    return LocationResponse.model_validate(location)


@router.delete(
    "/{location_id}",
    response_model=LocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a location",
    description="Soft-delete a location. Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Location not found"},
    },
)
async def delete_location(
    location_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.ADMIN)
    ),
) -> LocationResponse:
    """Soft-delete a location.

    Only Admins can delete locations.
    """
    stmt = SoftDeleteQuery.active(
        select(Location).filter(Location.id == location_id), Location
    )
    result = await db.execute(stmt)
    location = result.scalar_one_or_none()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    location.soft_delete(deleted_by=str(current_user.id))
    await db.commit()
    return LocationResponse.model_validate(location)
