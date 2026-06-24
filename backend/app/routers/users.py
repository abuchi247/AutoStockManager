"""User management router (Admin only).

Provides the following endpoints:
- GET  /api/v1/users       - List all users (Admin only)
- POST /api/v1/users       - Create a new user (Admin only)
- GET  /api/v1/users/{id}  - Get user by ID (Admin only)

Satisfies Requirements: 2.1, 17.1
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DbSession, AppSettings
from app.middleware.auth import require_roles
from app.models.user import User, UserRole
from app.schemas.auth import ErrorResponse
from app.schemas.user import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services.auth_service import (
    PasswordValidationError,
    hash_password,
    validate_password_complexity,
)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get(
    "",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all users",
    description="Retrieve a paginated list of all active users. Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
    },
)
async def list_users(
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> UserListResponse:
    """List all users with pagination.

    Requirements:
    - 2.1: Admin can view all users
    - 17.1: Enforce RBAC (Admin only)
    """
    # Count total active users
    count_stmt = select(func.count(User.id)).filter(User.deleted_at.is_(None))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch paginated users
    offset = (page - 1) * page_size
    stmt = (
        select(User)
        .filter(User.deleted_at.is_(None))
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    return UserListResponse(
        data=[UserResponse.model_validate(u) for u in users],
        meta={"page": page, "total": total, "page_size": page_size},
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description="Create a new user account with role assignment. Admin only.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        409: {"model": ErrorResponse, "description": "Username or email already exists"},
    },
)
async def create_user(
    request: UserCreate,
    db: DbSession,
    settings: AppSettings,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> UserResponse:
    """Create a new user account.

    Requirements:
    - 2.1: Support four roles (Admin, Manager, Salesperson, Storekeeper)
    - 2.5: Enforce password complexity
    - 17.1: Enforce RBAC (Admin only)
    """
    # Validate password complexity
    is_valid, error_msg = validate_password_complexity(request.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Check for duplicate username
    existing_username = await db.execute(
        select(User).filter_by(username=request.username, deleted_at=None)
    )
    if existing_username.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # Check for duplicate email
    existing_email = await db.execute(
        select(User).filter_by(email=request.email, deleted_at=None)
    )
    if existing_email.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    # Create user
    new_user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password, settings),
        role=request.role.value,
        is_active=request.is_active,
        created_by=str(current_user.id),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user by ID",
    description="Retrieve a single user by their ID. Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
async def get_user(
    user_id: UUID,
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> UserResponse:
    """Get a single user by ID.

    Requirements:
    - 17.1: Enforce RBAC (Admin only)
    """
    result = await db.execute(
        select(User).filter_by(id=user_id, deleted_at=None)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a user",
    description="Update user details (email, role, active status). Admin only.",
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "User not found"},
        409: {"model": ErrorResponse, "description": "Email already exists"},
    },
)
async def update_user(
    user_id: UUID,
    request: UserUpdate,
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> UserResponse:
    """Update a user's profile.

    Requirements:
    - 2.1: Admin can manage users
    - 17.1: Enforce RBAC (Admin only)
    """
    result = await db.execute(
        select(User).filter_by(id=user_id, deleted_at=None)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update fields if provided
    if request.email is not None and request.email != user.email:
        # Check for duplicate email
        existing_email = await db.execute(
            select(User).filter_by(email=request.email, deleted_at=None)
        )
        if existing_email.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )
        user.email = request.email

    if request.username is not None and request.username != user.username:
        # Check for duplicate username
        existing_username = await db.execute(
            select(User).filter_by(username=request.username, deleted_at=None)
        )
        if existing_username.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )
        user.username = request.username

    if request.role is not None:
        user.role = request.role.value

    if request.is_active is not None:
        user.is_active = request.is_active

    user.updated_by = str(current_user.id)

    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)
