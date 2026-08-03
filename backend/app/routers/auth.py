"""Authentication router with login, refresh, logout, and password reset endpoints.

Provides the following endpoints:
- POST /api/v1/auth/login          - Authenticate and issue JWT tokens
- POST /api/v1/auth/refresh        - Refresh access token using refresh token
- POST /api/v1/auth/logout         - Invalidate refresh token
- POST /api/v1/auth/reset-password - Request a password reset link
- POST /api/v1/auth/reset-password/confirm - Reset password with token

Refresh credentials never appear in a JSON response. Login sets an HTTP-only
cookie, refresh rotates it, and logout expires it. The request-body flow remains
available for non-browser API clients.

Satisfies Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.3, 3.4, 3.5, 17.3, 17.4, 17.5, 17.6
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DbSession, AppSettings
from app.refresh_cookie import (
    assert_trusted_origin,
    clear_refresh_cookie,
    refresh_cookie_deletion_headers,
    resolve_refresh_token,
    set_refresh_cookie,
)
from app.schemas.auth import (
    ErrorResponse,
    ForceChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordChangeRequiredResponse,
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
from app.middleware.rate_limit import auth_rate_limit
from app.services.password_reset_service import RedisPasswordResetJobQueue
from app.services.session_service import SessionService, get_redis_client

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


async def _get_auth_service(db: AsyncSession, settings) -> AuthService:
    """Create AuthService with session service integration."""
    redis_client = await get_redis_client()
    session_service = SessionService(db=db, redis_client=redis_client, settings=settings)
    password_reset_queue = RedisPasswordResetJobQueue(
        redis_client=redis_client,
        settings=settings,
    )
    return AuthService(
        db=db,
        settings=settings,
        session_service=session_service,
        password_reset_queue=password_reset_queue,
    )


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
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue tokens",
    description=(
        "Validates user credentials, returns the JWT access token, and sets the "
        "refresh credential in an HTTP-only cookie. If the user must change their "
        "password, returns a 200 with password_change_required=true and a scoped token."
    ),
    responses={
        200: {
            "description": "Successful authentication or password change required",
            "content": {
                "application/json": {
                    "examples": {
                        "normal_login": {
                            "summary": "Normal login",
                            "value": {"access_token": "eyJ...", "token_type": "bearer"},
                        },
                        "password_change_required": {
                            "summary": "Password change required",
                            "value": {
                                "password_change_required": True,
                                "password_change_token": "eyJ...",
                                "message": "Password change required before first access",
                            },
                        },
                    }
                }
            },
        },
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        423: {"model": ErrorResponse, "description": "Account locked"},
    },
)
@auth_rate_limit("rate_limit_login")
async def login(
    login_request: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> TokenResponse | PasswordChangeRequiredResponse:
    """Authenticate user with username/password and issue JWT tokens.

    Requirements:
    - 2.2: Issue JWT access token + refresh token on successful login
    - 2.8: Account lockout after 5 failed attempts within 15 minutes
    - 3.1: Deliver the refresh token as an HTTP-only, Secure, SameSite cookie
    - 3.5: Keep the refresh credential out of the JSON response
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

        # If the user must change their password, return the scoped token
        if result.get("password_change_required"):
            return PasswordChangeRequiredResponse(
                password_change_required=True,
                password_change_token=result["password_change_token"],
                message=result["message"],
            )

        set_refresh_cookie(response, result["refresh_token"], settings)
        return TokenResponse(
            access_token=result["access_token"],
            token_type=result["token_type"],
        )
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
    description=(
        "Exchange the refresh credential for a new access token. Browsers send "
        "the HTTP-only refresh cookie and no request body; non-browser clients "
        "may send the token in the body instead."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
        403: {"model": ErrorResponse, "description": "Untrusted request origin"},
    },
)
@auth_rate_limit("rate_limit_refresh")
async def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    refresh_request: RefreshTokenRequest | None = None,
) -> TokenResponse:
    """Refresh access token without re-entering credentials.

    Requirements:
    - 2.3: Allow token refresh using valid refresh token
    - 3.3: Obtain a new access token using the HTTP-only refresh cookie
    - 3.5: Read the credential from the cookie, keep body support for API clients
    - 17.3: Validate against session registry, rotate session
    """
    body_token = refresh_request.refresh_token if refresh_request else None
    refresh_token_str, from_cookie = resolve_refresh_token(
        request, body_token, settings
    )

    if from_cookie:
        # Cookie authentication is ambient, so the browser-declared origin is
        # validated before any state change.
        assert_trusted_origin(request, settings)

    if refresh_token_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh credential is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = await _get_auth_service(db, settings)
    ip_address = _get_client_ip(request)
    user_agent = _get_user_agent(request)

    try:
        result = await auth_service.refresh_token(
            refresh_token_str=refresh_token_str,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except AuthenticationError as e:
        headers = {"WWW-Authenticate": "Bearer"}
        if from_cookie:
            # A rejected cookie is unusable; expire it so the browser stops
            # replaying it on every request.
            headers.update(refresh_cookie_deletion_headers(settings))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers=headers,
        )

    # Rotate the cookie alongside the rotated Redis session entry.
    set_refresh_cookie(response, result["refresh_token"], settings)
    return TokenResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout and invalidate refresh token",
    description=(
        "Expires the refresh cookie and removes the session from the registry. "
        "Browsers send no request body; non-browser clients may send the token."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
        403: {"model": ErrorResponse, "description": "Untrusted request origin"},
    },
)
async def logout(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    logout_request: LogoutRequest | None = None,
) -> MessageResponse:
    """Invalidate refresh token and remove session from registry.

    Requirements:
    - 3.4: Clear the refresh cookie and invalidate the session entry
    - 3.5: Accept the credential from the cookie, keep body support for API clients
    - 17.4: Invalidate refresh token and remove from session registry on logout
    """
    body_token = logout_request.refresh_token if logout_request else None
    refresh_token_str, from_cookie = resolve_refresh_token(
        request, body_token, settings
    )

    if from_cookie:
        assert_trusted_origin(request, settings)

    # The browser must end up without a refresh cookie in every outcome.
    clear_refresh_cookie(response, settings)

    if refresh_token_str is None:
        # Nothing to revoke; logout stays idempotent for already-cleared clients.
        return MessageResponse(message="Successfully logged out")

    auth_service = await _get_auth_service(db, settings)

    try:
        result = await auth_service.logout(refresh_token_str=refresh_token_str)
    except AuthenticationError as e:
        headers = {"WWW-Authenticate": "Bearer"}
        if from_cookie:
            headers.update(refresh_cookie_deletion_headers(settings))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers=headers,
        )

    return MessageResponse(**result)


@router.post(
    "/reset-password",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description=(
        "Request a password reset link. The same generic response is returned "
        "whether or not the email belongs to an account."
    ),
)
@auth_rate_limit("rate_limit_password_reset")
async def request_password_reset(
    reset_request: PasswordResetRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> PasswordResetResponse:
    """Queue a password-reset email and always return the generic response."""
    auth_service = await _get_auth_service(db, settings)
    result = await auth_service.request_password_reset(email=reset_request.email)
    return PasswordResetResponse(**result)


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
@auth_rate_limit("rate_limit_password_reset_confirm")
async def confirm_password_reset(
    confirm_request: PasswordResetConfirm,
    request: Request,
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


@router.post(
    "/force-change-password",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password (first login)",
    description=(
        "Complete the forced password change for accounts that require it. "
        "Accepts the scoped password_change_token issued at login and the new "
        "password. On success, returns normal access/refresh tokens so the user "
        "is immediately authenticated."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Password validation failed"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
@auth_rate_limit("rate_limit_login")
async def force_change_password(
    body: ForceChangePasswordRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> TokenResponse:
    """Change password for a user who must set a new password before first access.

    This endpoint is only usable with the scoped password_change token returned
    by the login endpoint when must_change_password is True. After the password
    is changed, the user receives normal tokens and is fully authenticated.
    """
    auth_service = await _get_auth_service(db, settings)
    ip_address = _get_client_ip(request)
    user_agent = _get_user_agent(request)

    try:
        result = await auth_service.force_change_password(
            token=body.password_change_token,
            new_password=body.new_password,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()
        set_refresh_cookie(response, result["refresh_token"], settings)
        return TokenResponse(
            access_token=result["access_token"],
            token_type=result["token_type"],
        )
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
