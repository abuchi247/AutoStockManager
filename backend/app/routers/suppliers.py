"""Supplier management router with CRUD, balance, and aging endpoints.

Provides the following endpoints:
- GET    /api/v1/suppliers              - List all suppliers (paginated)
- POST   /api/v1/suppliers              - Create a new supplier
- GET    /api/v1/suppliers/{id}         - Get supplier by ID
- PUT    /api/v1/suppliers/{id}         - Update a supplier
- DELETE /api/v1/suppliers/{id}         - Soft-delete a supplier
- GET    /api/v1/suppliers/{id}/balance - Get supplier balance
- GET    /api/v1/suppliers/{id}/aging   - Get supplier aging analysis

Satisfies Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.supplier import (
    SupplierBalanceResponse,
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.supplier_service import (
    SupplierNotFoundError,
    SupplierService,
)

router = APIRouter(prefix="/api/v1/suppliers", tags=["Suppliers"])


def _get_supplier_service(db) -> SupplierService:
    """Create a SupplierService instance."""
    return SupplierService(db=db)


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=SupplierListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all suppliers",
    description="Retrieve a paginated list of all active suppliers.",
)
async def list_suppliers(
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(
        default=None, description="Search by name, contact person, phone, or email"
    ),
) -> SupplierListResponse:
    """List all active suppliers with pagination.

    Accessible by Manager and Admin roles only.
    """
    service = _get_supplier_service(db)
    suppliers, total = await service.list_suppliers(
        page=page, page_size=page_size, search=search
    )

    return SupplierListResponse(
        data=[SupplierResponse.model_validate(s) for s in suppliers],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new supplier",
    description="Create a new supplier record. Manager or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    },
)
async def create_supplier(
    request: SupplierCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SupplierResponse:
    """Create a new supplier.

    Requirement 8.1: Store supplier profiles with all required attributes.
    """
    service = _get_supplier_service(db)

    supplier = await service.create_supplier(
        data=request,
        created_by=str(current_user.id),
    )
    await db.commit()
    await db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Get supplier by ID",
    description="Retrieve a single supplier by its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "Supplier not found"},
    },
)
async def get_supplier(
    supplier_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SupplierResponse:
    """Get a single supplier by ID.

    Accessible by Manager and Admin roles.
    """
    service = _get_supplier_service(db)

    try:
        supplier = await service.get_supplier(supplier_id)
        return SupplierResponse.model_validate(supplier)
    except SupplierNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )


@router.put(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a supplier",
    description="Update an existing supplier's attributes.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        404: {"model": ErrorResponse, "description": "Supplier not found"},
    },
)
async def update_supplier(
    supplier_id: UUID,
    request: SupplierUpdate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SupplierResponse:
    """Update a supplier's attributes (partial update).

    Accessible by Manager and Admin roles.
    """
    service = _get_supplier_service(db)

    try:
        supplier = await service.update_supplier(
            supplier_id=supplier_id,
            data=request,
            updated_by=str(current_user.id),
        )
        await db.commit()
        await db.refresh(supplier)
        return SupplierResponse.model_validate(supplier)
    except SupplierNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )


@router.delete(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a supplier",
    description="Soft-delete a supplier. Manager or Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Supplier not found"},
    },
)
async def delete_supplier(
    supplier_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SupplierResponse:
    """Soft-delete a supplier.

    Only Managers and Admins can delete suppliers.
    """
    service = _get_supplier_service(db)

    try:
        supplier = await service.delete_supplier(
            supplier_id=supplier_id,
            deleted_by=str(current_user.id),
        )
        await db.commit()
        return SupplierResponse.model_validate(supplier)
    except SupplierNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )


@router.get(
    "/{supplier_id}/balance",
    response_model=SupplierBalanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get supplier balance",
    description="Get the current outstanding balance for a supplier.",
    responses={
        404: {"model": ErrorResponse, "description": "Supplier not found"},
    },
)
async def get_supplier_balance(
    supplier_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SupplierBalanceResponse:
    """Get the current outstanding balance for a supplier.

    Requirement 8.3: Calculate the current supplier balance as the sum
    of all purchase and payment entries for that supplier.

    Accessible by Manager and Admin roles.
    """
    service = _get_supplier_service(db)

    try:
        supplier = await service.get_supplier(supplier_id)
        balance = await service.calculate_balance(supplier_id)
        aging = await service.calculate_aging(supplier_id)

        return SupplierBalanceResponse(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            total_balance=balance,
            aging=aging,
        )
    except SupplierNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )


@router.get(
    "/{supplier_id}/aging",
    response_model=SupplierBalanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get supplier aging analysis",
    description="Get aging analysis for a supplier's outstanding balance.",
    responses={
        404: {"model": ErrorResponse, "description": "Supplier not found"},
    },
)
async def get_supplier_aging(
    supplier_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> SupplierBalanceResponse:
    """Get aging analysis for a supplier's outstanding balance.

    Requirement 8.4: Calculate supplier aging analysis categorizing
    outstanding amounts into current, 1-30 days, 31-60 days, 61-90 days,
    and over 90 days overdue.

    Accessible by Manager and Admin roles.
    """
    service = _get_supplier_service(db)

    try:
        supplier = await service.get_supplier(supplier_id)
        balance = await service.calculate_balance(supplier_id)
        aging = await service.calculate_aging(supplier_id)

        return SupplierBalanceResponse(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            total_balance=balance,
            aging=aging,
        )
    except SupplierNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )
