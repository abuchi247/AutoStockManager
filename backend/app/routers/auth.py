"""Authentication router with login, refresh, logout, and password reset endpoints.

Provides the following endpoints:
- POST /api/v1/auth/login          - Authenticate and issue JWT tokens
- POST /api/v1/auth/refresh        - Refresh access token using refresh token
- POST /api/v1/auth/logout         - Invalidate refresh token
- POST /api/v1/auth/reset-password - Request password reset token
- POST /api/v1/auth/reset-password/confirm - Reset password with token

Satisfies Requirements: 2.1, 2.2, 2.3, 2.4, 17.3, 17.4, 17.5, 17.6
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DbSession, AppSettings
from app.schemas.auth import (
    ErrorResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetResponse,
    RefreshTokenRequest,
    TokenResponse,
)
from app.services.auth_service import (
    AccountLockedError,
    AuthenticationError,
    AuthService,
    PasswordValidationError,
)
from app.services.session_service import SessionService, get_redis_client

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


async def _get_auth_service(db: AsyncSession, settings) -> AuthService:
    """Create AuthService with session service integration."""
    redis_client = await get_redis_client()
    session_service = SessionService(db=db, redis_client=redis_client, settings=settings)
    return AuthService(db=db, settings=settings, session_service=session_service)


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP from request."""
    # Check X-Forwarded-For for proxied requests
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _get_user_agent(request: Request) -> str | None:
    """Extract user agent from request."""
    return request.headers.get("user-agent")


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue tokens",
    description="Validates user credentials and returns JWT access and refresh tokens.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        423: {"model": ErrorResponse, "description": "Account locked"},
    },
)
async def login(
    login_request: LoginRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> TokenResponse:
    """Authenticate user with username/password and issue JWT tokens.

    Requirements:
    - 2.2: Issue JWT access token + refresh token on successful login
    - 2.8: Account lockout after 5 failed attempts within 15 minutes
    - 17.3: Register session in Redis on success
    - 17.5: Record login history (timestamp, IP, user agent, success/failure)
    """
    auth_service = await _get_auth_service(db, settings)
    ip_address = _get_client_ip(request)
    user_agent = _get_user_agent(request)

    try:
        result = await auth_service.login(
            username=login_request.username,
            password=login_request.password,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()
        return TokenResponse(**result)
    except AccountLockedError as e:
        await db.commit()  # Persist the lockout state
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=e.message,
        )
    except AuthenticationError as e:
        await db.commit()  # Persist failed attempt count + login history
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access/refresh token pair.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
    },
)
async def refresh(
    refresh_request: RefreshTokenRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> TokenResponse:
    """Refresh access token without re-entering credentials.

    Requirements:
    - 2.3: Allow token refresh using valid refresh token
    - 17.3: Validate against session registry, rotate session
    """
    auth_service = await _get_auth_service(db, settings)
    ip_address = _get_client_ip(request)
    user_agent = _get_user_agent(request)

    try:
        result = await auth_service.refresh_token(
            refresh_token_str=refresh_request.refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return TokenResponse(**result)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout and invalidate refresh token",
    description="Invalidates the provided refresh token, removing the session from registry.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
    },
)
async def logout(
    logout_request: LogoutRequest,
    db: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    """Invalidate refresh token and remove session from registry.

    Requirements:
    - 17.4: Invalidate refresh token and remove from session registry on logout
    """
    auth_service = await _get_auth_service(db, settings)

    try:
        result = await auth_service.logout(
            refresh_token_str=logout_request.refresh_token,
        )
        return MessageResponse(**result)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/reset-password",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Generate a time-limited password reset token for the given email.",
    responses={
        404: {"model": ErrorResponse, "description": "Email not found"},
    },
)
async def request_password_reset(
    reset_request: PasswordResetRequest,
    db: DbSession,
    settings: AppSettings,
) -> PasswordResetResponse:
    """Generate password reset token for the user's email.

    Requirements:
    - 2.4: Generate time-limited reset token, invalidate previous tokens
    """
    auth_service = await _get_auth_service(db, settings)

    try:
        result = await auth_service.request_password_reset(email=reset_request.email)
        return PasswordResetResponse(**result)
    except AuthenticationError:
        # Return generic response to prevent email enumeration
        # In production, always return success regardless
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="If the email exists, a reset link will be sent",
        )


@router.post(
    "/reset-password/confirm",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset",
    description="Reset user password using a valid reset token.",
    responses={
        400: {"model": ErrorResponse, "description": "Password validation failed"},
        401: {"model": ErrorResponse, "description": "Invalid or expired reset token"},
    },
)
async def confirm_password_reset(
    confirm_request: PasswordResetConfirm,
    db: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    """Reset password using valid reset token and new password.

    Requirements:
    - 2.4: Reset password with valid token
    - 2.5: Enforce password complexity
    """
    auth_service = await _get_auth_service(db, settings)

    try:
        result = await auth_service.reset_password(
            reset_token=confirm_request.reset_token,
            new_password=confirm_request.new_password,
        )
        await db.commit()
        return MessageResponse(**result)
    except PasswordValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )
