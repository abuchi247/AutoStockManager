"""Customer management router with CRUD, purchase history, ledger, and aging endpoints.

Provides the following endpoints:
- GET    /api/v1/customers              - List all customers (paginated)
- POST   /api/v1/customers              - Create a new customer
- GET    /api/v1/customers/{id}         - Get customer by ID
- PUT    /api/v1/customers/{id}         - Update a customer
- DELETE /api/v1/customers/{id}         - Soft-delete a customer
- GET    /api/v1/customers/{id}/purchase-history - Get purchase history
- GET    /api/v1/customers/{id}/ledger  - Get credit ledger entries
- GET    /api/v1/customers/{id}/aging   - Get aging analysis

Satisfies Requirements: 6.1, 6.2, 6.3, 7.1, 7.3
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.customer_credit_ledger import CustomerCreditLedger
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.credit import (
    AgingAnalysisResponse,
    CreditLedgerEntryResponse,
    CreditLedgerListResponse,
)
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
    PurchaseHistoryItem,
    PurchaseHistoryResponse,
)
from app.services.credit_ledger_service import CreditLedgerService
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
    account_status: Optional[str] = Query(
        default=None, description="Filter by account status (active, suspended, closed)"
    ),
) -> CustomerListResponse:
    """List all active customers with pagination.

    Accessible by Salesperson, Manager, and Admin roles.
    """
    service = _get_customer_service(db)
    customers, total = await service.list_customers(
        page=page, page_size=page_size, search=search, account_status=account_status
    )

    # Compute balance from credit ledger for each customer
    customer_ids = [c.id for c in customers]
    balance_map: dict = {}
    if customer_ids:
        balance_stmt = (
            select(
                CustomerCreditLedger.customer_id,
                func.sum(CustomerCreditLedger.amount).label("balance"),
            )
            .filter(CustomerCreditLedger.customer_id.in_(customer_ids))
            .group_by(CustomerCreditLedger.customer_id)
        )
        balance_result = await db.execute(balance_stmt)
        for row in balance_result.all():
            balance_map[row.customer_id] = float(row.balance or 0)

    data = []
    for c in customers:
        resp = CustomerResponse.model_validate(c)
        resp.balance = balance_map.get(c.id, 0.0)
        data.append(resp)

    return CustomerListResponse(
        data=data,
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
        resp = CustomerResponse.model_validate(customer)

        # Compute balance from credit ledger
        balance_stmt = (
            select(func.sum(CustomerCreditLedger.amount).label("balance"))
            .filter(CustomerCreditLedger.customer_id == customer_id)
        )
        balance_result = await db.execute(balance_stmt)
        balance_row = balance_result.scalar()
        resp.balance = float(balance_row) if balance_row is not None else 0.0

        return resp
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


# =============================================================================
# Credit Ledger & Aging Endpoints
# =============================================================================


@router.get(
    "/{customer_id}/ledger",
    response_model=CreditLedgerListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer credit ledger",
    description="Retrieve credit ledger entries for a customer. Manager/Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Customer not found"},
    },
)
async def get_customer_ledger(
    customer_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> CreditLedgerListResponse:
    """Get credit ledger entries for a customer.

    Requirement 7.1: THE Credit_Ledger SHALL record entries for the following
    transaction types: sale, payment, adjustment, and return.

    Accessible by Manager and Admin roles.
    """
    # Verify customer exists
    service = _get_customer_service(db)
    try:
        await service.get_customer(customer_id)
    except CustomerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    # Query ledger entries with pagination
    offset = (page - 1) * page_size

    # Get total count
    count_stmt = (
        select(func.count(CustomerCreditLedger.id))
        .filter(CustomerCreditLedger.customer_id == customer_id)
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get paginated entries ordered by created_at descending (newest first)
    stmt = (
        select(CustomerCreditLedger)
        .filter(CustomerCreditLedger.customer_id == customer_id)
        .order_by(CustomerCreditLedger.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()

    return CreditLedgerListResponse(
        data=[CreditLedgerEntryResponse.model_validate(e) for e in entries],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.get(
    "/{customer_id}/aging",
    response_model=AgingAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get customer aging analysis",
    description="Get aging analysis for a customer's outstanding balance. Manager/Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Customer not found"},
    },
)
async def get_customer_aging(
    customer_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> AgingAnalysisResponse:
    """Get aging analysis for a customer.

    Requirement 7.3: THE Credit_Ledger SHALL calculate aging analysis for
    each customer categorizing outstanding amounts into current, 1-30 days,
    31-60 days, 61-90 days, and over 90 days overdue.

    Accessible by Manager and Admin roles.
    """
    # Verify customer exists
    service = _get_customer_service(db)
    try:
        await service.get_customer(customer_id)
    except CustomerNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    # Calculate aging analysis
    credit_service = CreditLedgerService(db=db)
    aging = await credit_service.aging_analysis(customer_id)

    return AgingAnalysisResponse(
        customer_id=customer_id,
        current=aging["current"],
        days_1_30=aging["1_30_days"],
        days_31_60=aging["31_60_days"],
        days_61_90=aging["61_90_days"],
        over_90_days=aging["over_90_days"],
        total=aging["total"],
    )
