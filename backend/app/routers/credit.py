"""Credit management router with payment and adjustment endpoints.

Provides the following endpoints:
- POST /api/v1/credit/payments     - Record a customer payment
- POST /api/v1/credit/adjustments  - Record a manual adjustment (Manager/Admin only)

Satisfies Requirements: 6.3, 7.1, 7.5
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.customer import Customer
from app.models.customer_credit_ledger import CreditTransactionType
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.credit import (
    AdjustmentCreate,
    AdjustmentResponse,
    CreditLedgerEntryResponse,
    PaymentCreate,
    PaymentResponse,
)
from app.services.credit_ledger_service import CreditLedgerService, CreditLimitExceededError

router = APIRouter(prefix="/api/v1/credit", tags=["Credit"])


def _get_credit_service(db) -> CreditLedgerService:
    """Create a CreditLedgerService instance."""
    return CreditLedgerService(db=db)


async def _get_customer_or_404(db, customer_id: uuid.UUID) -> Customer:
    """Load a customer by ID or raise 404."""
    result = await db.execute(
        select(Customer).filter_by(id=customer_id, deleted_at=None)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return customer


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a customer payment",
    description="Record a payment that reduces the customer's outstanding balance.",
    responses={
        404: {"model": ErrorResponse, "description": "Customer not found"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    },
)
async def record_payment(
    request: PaymentCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.SALESPERSON, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> PaymentResponse:
    """Record a customer payment.

    Requirement 6.3: WHEN a customer payment is received, THE Credit_Ledger
    SHALL record a credit entry against the customer account reducing the
    outstanding balance.

    Accessible by Salesperson, Manager, and Admin roles.
    """
    # Verify customer exists
    await _get_customer_or_404(db, request.customer_id)

    service = _get_credit_service(db)

    import uuid as uuid_mod
    ref_id = request.sale_id or request.reference_id or uuid_mod.uuid4()

    entry = await service.record_credit(
        customer_id=request.customer_id,
        amount=request.amount,
        reference_type="payment",
        reference_id=ref_id,
        created_by=current_user.id,
        transaction_type=CreditTransactionType.PAYMENT,
        notes=request.notes,
    )

    await db.commit()
    await db.refresh(entry)

    # Calculate updated balance
    new_balance = await service.calculate_balance(request.customer_id)

    return PaymentResponse(
        entry=CreditLedgerEntryResponse.model_validate(entry),
        new_balance=new_balance,
    )


@router.post(
    "/adjustments",
    response_model=AdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a manual adjustment",
    description="Record a manual credit adjustment. Requires notes/reason. Manager/Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error or credit limit exceeded"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Customer not found"},
    },
)
async def record_adjustment(
    request: AdjustmentCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> AdjustmentResponse:
    """Record a manual credit adjustment.

    Requirement 7.5: THE Credit_Ledger SHALL support manual adjustments with
    a required reason field and Manager or Admin authorization.

    Requirement 7.8: WHEN a manual adjustment increases a customer outstanding
    balance, THE Credit_Ledger SHALL enforce credit limit validation.

    Only accessible by Manager and Admin roles.
    """
    # Verify customer exists and get credit limit for validation
    customer = await _get_customer_or_404(db, request.customer_id)

    service = _get_credit_service(db)

    import uuid as uuid_mod
    ref_id = request.reference_id or uuid_mod.uuid4()

    try:
        if request.amount > Decimal("0"):
            # Positive adjustment = debit (increases balance)
            # Must validate credit limit per Requirement 7.8
            entry = await service.record_debit(
                customer_id=request.customer_id,
                amount=request.amount,
                reference_type="adjustment",
                reference_id=ref_id,
                created_by=current_user.id,
                transaction_type=CreditTransactionType.ADJUSTMENT,
                notes=request.notes,
                credit_limit=customer.credit_limit,
            )
        else:
            # Negative adjustment = credit (decreases balance)
            entry = await service.record_credit(
                customer_id=request.customer_id,
                amount=abs(request.amount),
                reference_type="adjustment",
                reference_id=ref_id,
                created_by=current_user.id,
                transaction_type=CreditTransactionType.ADJUSTMENT,
                notes=request.notes,
            )
    except CreditLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    await db.commit()
    await db.refresh(entry)

    # Calculate updated balance
    new_balance = await service.calculate_balance(request.customer_id)

    return AdjustmentResponse(
        entry=CreditLedgerEntryResponse.model_validate(entry),
        new_balance=new_balance,
    )
