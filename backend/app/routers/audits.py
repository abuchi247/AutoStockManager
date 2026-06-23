"""Audit router for inventory audit session endpoints.

Provides the following endpoints:
- GET    /api/v1/audits                    - List audit sessions (paginated, filterable)
- POST   /api/v1/audits                    - Initiate a new audit session
- GET    /api/v1/audits/{id}               - Get single audit session with snapshot items
- POST   /api/v1/audits/{id}/counts        - Submit a physical count
- POST   /api/v1/audits/{id}/approve       - Complete/approve the audit
- GET    /api/v1/audits/{id}/reconciliation - Get post-snapshot movements
- GET    /api/v1/audits/{id}/recount-flags  - Get parts needing re-count

Satisfies Requirements: 11.1, 11.2, 11.3, 11.4
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import DbSession
from app.middleware.auth import require_roles
from app.models.audit_session import AuditType, AuditStatus
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.audit import (
    AuditCountResponse,
    AuditCountSubmit,
    AuditSessionCreate,
    AuditSessionListResponse,
    AuditSessionResponse,
    ReconciliationMovementResponse,
    ReconciliationResponse,
    RecountFlagResponse,
    RecountFlagsResponse,
)
from app.services.audit_service import (
    AuditService,
    AuditSessionNotFoundError,
    InvalidAuditStatusError,
    SnapshotItemNotFoundError,
)

router = APIRouter(prefix="/api/v1/audits", tags=["Audits"])


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "",
    response_model=AuditSessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List audit sessions",
    description="Retrieve a paginated list of audit sessions, optionally filtered by location and/or status. Accessible by Storekeeper, Manager, and Admin.",
)
async def list_audits(
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    location_id: Optional[UUID] = Query(
        default=None,
        description="Filter by location UUID",
    ),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by session status (INITIATED, IN_PROGRESS, COMPLETED, CANCELLED)",
    ),
) -> AuditSessionListResponse:
    """List all audit sessions with optional filtering and pagination.

    Accessible by Storekeeper, Manager, and Admin roles.
    """
    service = AuditService(db)

    # Parse status filter if provided
    parsed_status = None
    if status_filter:
        try:
            parsed_status = AuditStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter: '{status_filter}'. Valid values: INITIATED, IN_PROGRESS, COMPLETED, CANCELLED",
            )

    sessions, total = await service.list_sessions(
        location_id=location_id,
        status_filter=parsed_status,
        page=page,
        page_size=page_size,
    )

    return AuditSessionListResponse(
        data=[AuditSessionResponse.model_validate(s) for s in sessions],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "",
    response_model=AuditSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate an audit session",
    description="Create a new audit session by capturing a snapshot of current stock quantities. Storekeeper, Manager, or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    },
)
async def create_audit(
    request: AuditSessionCreate,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> AuditSessionResponse:
    """Initiate a new audit session.

    Requirements:
    - 11.1: Support CYCLE_COUNT and FULL_STOCK_COUNT audit types
    - 11.2: Create session recording audit_type, location, date, and assigned users
    """
    service = AuditService(db)

    try:
        audit_type = AuditType(request.audit_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid audit_type: '{request.audit_type}'. Must be CYCLE_COUNT or FULL_STOCK_COUNT",
        )

    session = await service.initiate_audit(
        location_id=request.location_id,
        audit_type=audit_type,
        initiated_by=current_user.id,
        spare_part_ids=request.spare_part_ids,
    )
    await db.commit()
    await db.refresh(session)
    return AuditSessionResponse.model_validate(session)


@router.get(
    "/{session_id}",
    response_model=AuditSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get audit session by ID",
    description="Retrieve a single audit session with its snapshot items and counts.",
    responses={
        404: {"model": ErrorResponse, "description": "Audit session not found"},
    },
)
async def get_audit(
    session_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> AuditSessionResponse:
    """Get a single audit session by its ID.

    Accessible by Storekeeper, Manager, and Admin roles.
    """
    service = AuditService(db)

    try:
        session = await service._get_session(session_id)
    except AuditSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit session not found",
        )

    return AuditSessionResponse.model_validate(session)


@router.post(
    "/{session_id}/counts",
    response_model=AuditCountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a physical count",
    description="Submit a physical count for a spare part in an active audit session. Storekeeper only.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid session state or part not in snapshot"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Audit session not found"},
    },
)
async def submit_count(
    session_id: UUID,
    request: AuditCountSubmit,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> AuditCountResponse:
    """Submit a physical count for a spare part.

    Requirements:
    - 11.3: Calculate variance as counted_quantity - system_quantity (snapshot)
    """
    service = AuditService(db)

    try:
        audit_count = await service.submit_count(
            session_id=session_id,
            spare_part_id=request.spare_part_id,
            counted_quantity=request.counted_quantity,
            counted_by=current_user.id,
        )
        await db.commit()
        await db.refresh(audit_count)
        return AuditCountResponse.model_validate(audit_count)
    except AuditSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit session not found",
        )
    except InvalidAuditStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except SnapshotItemNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{session_id}/approve",
    response_model=AuditSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete/approve an audit",
    description="Complete an audit session by creating adjustment ledger entries for non-zero variances. Manager or Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid session state"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Audit session not found"},
    },
)
async def approve_audit(
    session_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> AuditSessionResponse:
    """Complete/approve an audit session.

    Requirements:
    - 11.4: Complete audit creates adjustment entries in ledger
    """
    service = AuditService(db)

    try:
        session = await service.complete_audit(
            session_id=session_id,
            approved_by=current_user.id,
        )
        await db.commit()
        await db.refresh(session)
        return AuditSessionResponse.model_validate(session)
    except AuditSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit session not found",
        )
    except InvalidAuditStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{session_id}/reconciliation",
    response_model=ReconciliationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get reconciliation view",
    description="Get post-snapshot movements for auditor review. Shows all stock movements at the audit location after the snapshot timestamp.",
    responses={
        404: {"model": ErrorResponse, "description": "Audit session not found"},
    },
)
async def get_reconciliation(
    session_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> ReconciliationResponse:
    """Get the reconciliation view showing post-snapshot movements.

    Accessible by Storekeeper, Manager, and Admin roles.
    """
    service = AuditService(db)

    try:
        movements = await service.get_reconciliation_view(session_id=session_id)
    except AuditSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit session not found",
        )

    return ReconciliationResponse(
        session_id=session_id,
        movements=[
            ReconciliationMovementResponse(
                ledger_entry_id=m.ledger_entry_id,
                spare_part_id=m.spare_part_id,
                quantity_change=m.quantity_change,
                movement_type=m.movement_type,
                reference_type=m.reference_type,
                reference_id=m.reference_id,
                created_at=m.created_at,
                created_by=m.created_by,
            )
            for m in movements
        ],
    )


@router.get(
    "/{session_id}/recount-flags",
    response_model=RecountFlagsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get parts needing re-count",
    description="Get spare parts that had stock movements during the active audit, requiring re-count verification.",
    responses={
        404: {"model": ErrorResponse, "description": "Audit session not found"},
    },
)
async def get_recount_flags(
    session_id: UUID,
    db: DbSession,
    current_user: User = Depends(
        require_roles(UserRole.STOREKEEPER, UserRole.MANAGER, UserRole.ADMIN)
    ),
) -> RecountFlagsResponse:
    """Get parts flagged as needing re-count.

    Accessible by Storekeeper, Manager, and Admin roles.
    """
    service = AuditService(db)

    try:
        flags = await service.check_recount_required(session_id=session_id)
    except AuditSessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit session not found",
        )

    return RecountFlagsResponse(
        session_id=session_id,
        flags=[
            RecountFlagResponse(
                spare_part_id=f.spare_part_id,
                movement_count=f.movement_count,
                net_quantity_change=f.net_quantity_change,
            )
            for f in flags
        ],
    )
