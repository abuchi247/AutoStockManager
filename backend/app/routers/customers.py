"""Customer management router with CRUD and purchase history endpoints.

Provides the following endpoints:
- GET    /api/v1/customers              - List all customers (paginated)
- POST   /api/v1/customers              - Create a new customer
- GET    /api/v1/customers/{id}         - Get customer by ID
- PUT    /api/v1/customers/{id}         - Update a customer
- DELETE /api/v1/customers/{id}         - Soft-delete a customer
- GET    /api/v1/customers/{id}/purchase-history - Get purchase history

Satisfies Requirements: 6.1, 6.2
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
    PurchaseHistoryItem,
    PurchaseHistoryResponse,
)
from app.services.customer_service import (
    CustomerNotFoundError,
    CustomerService,
)

router = APIRouter(prefix="/api/v1/customers", tags=["Customers"])


def _get_customer_service(db) -> CustomerService:
    """Create a CustomerService instance."""
    return CustomerService(db=db)


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=CustomerListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all customers",
    description="Retrieve a paginated list of all active customers.",
)
async def list_customers(
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(
        default=None, description="Search by name, phone, or email"
    ),
) -> CustomerListResponse:
    """List all active customers with pagination.

    Accessible by Salesperson, Manager, and Admin roles.
    """
    service = _get_customer_service(db)
    customers, total = await service.list_customers(
        page=page, page_size=page_size, search=search
    )

    return CustomerListResponse(
        data=[CustomerResponse.model_validate(c) for c in customers],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer",
    description="Create a new customer record. Salesperson, Manager, or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    },
)
async def create_customer(
    request: CustomerCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> CustomerResponse:
    """Create a new customer.

    Requirement 6.1: Store customer profiles with all required attributes.
    """
    service = _get_customer_service(db)

    customer = await service.create_customer(
        data=request,
        created_by=str(current_user.id),
    )
    await db.commit()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer by ID",
    description="Retrieve a single customer by its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "Customer not found"},
    },
)
async def get_customer(
    customer_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> CustomerResponse:
    """Get a single customer by ID.

    Accessible by all authenticated users.
    """
    service = _get_customer_service(db)

    try:
        customer = await service.get_customer(customer_id)
        return CustomerResponse.model_validate(customer)
    except CustomerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a customer",
    description="Update an existing customer's attributes.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        404: {"model": ErrorResponse, "description": "Customer not found"},
    },
)
async def update_customer(
    customer_id: UUID,
    request: CustomerUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> CustomerResponse:
    """Update a customer's attributes (partial update)."""
    service = _get_customer_service(db)

    try:
        customer = await service.update_customer(
            customer_id=customer_id,
            data=request,
            updated_by=str(current_user.id),
        )
        await db.commit()
        await db.refresh(customer)
        return CustomerResponse.model_validate(customer)
    except CustomerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )


@router.delete(
    "/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a customer",
    description="Soft-delete a customer. Manager or Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Customer not found"},
    },
)
async def delete_customer(
    customer_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> CustomerResponse:
    """Soft-delete a customer.

    Only Managers and Admins can delete customers.
    """
    service = _get_customer_service(db)

    try:
        customer = await service.delete_customer(
            customer_id=customer_id,
            deleted_by=str(current_user.id),
        )
        await db.commit()
        return CustomerResponse.model_validate(customer)
    except CustomerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )


@router.get(
    "/{customer_id}/purchase-history",
    response_model=PurchaseHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer purchase history",
    description="Retrieve the purchase history for a specific customer.",
    responses={
        404: {"model": ErrorResponse, "description": "Customer not found"},
    },
)
async def get_purchase_history(
    customer_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PurchaseHistoryResponse:
    """Get purchase history for a customer.

    Requirement 6.2: Maintain complete purchase history for each customer
    including all sales transactions, dates, amounts, and payment status.

    Accessible by all authenticated users.
    """
    service = _get_customer_service(db)

    try:
        sales, total = await service.get_purchase_history(
            customer_id=customer_id,
            page=page,
            page_size=page_size,
        )

        items = [
            PurchaseHistoryItem(
                sale_id=sale.id,
                invoice_number=sale.invoice_number,
                status=sale.status.value if hasattr(sale.status, 'value') else sale.status,
                payment_type=sale.payment_type.value if hasattr(sale.payment_type, 'value') else sale.payment_type,
                total_amount=sale.total_amount,
                created_at=sale.created_at,
            )
            for sale in sales
        ]

        return PurchaseHistoryResponse(
            data=items,
            meta={"page": page, "total": total, "page_size": page_size},
        )
    except CustomerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
