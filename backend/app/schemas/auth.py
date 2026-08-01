"""Pydantic schemas for authentication endpoints.

Defines request/response models for login, token refresh, logout,
and password reset operations.

Satisfies Requirements: 2.1, 2.2, 2.3, 2.4
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =============================================================================
# Request Schemas
# =============================================================================


class LoginRequest(BaseModel):
    """Request body for POST /api/v1/auth/login."""

    username: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="User's login username",
        examples=["admin"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="User's password",
        examples=["SecurePass1"],
    )


class RefreshTokenRequest(BaseModel):
    """Optional request body for POST /api/v1/auth/refresh.

    Browsers send the refresh credential in the HTTP-only cookie and omit the
    body entirely. This schema exists for non-browser API clients.
    """

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Valid refresh token to exchange for new token pair",
    )


class LogoutRequest(BaseModel):
    """Optional request body for POST /api/v1/auth/logout.

    Browsers rely on the HTTP-only refresh cookie; this schema exists for
    non-browser API clients.
    """

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Refresh token to invalidate",
    )


class PasswordResetRequest(BaseModel):
    """Request body for POST /api/v1/auth/reset-password (initiate reset)."""

    email: EmailStr = Field(
        ...,
        description="Email address associated with the user account",
        examples=["admin@example.com"],
    )


class PasswordResetConfirm(BaseModel):
    """Request body for POST /api/v1/auth/reset-password/confirm."""

    reset_token: str = Field(
        ...,
        min_length=1,
        description="Password reset token received via email",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (min 8 chars, must include uppercase, lowercase, and digit)",
        examples=["NewSecure1"],
    )


# =============================================================================
# Response Schemas
# =============================================================================


class TokenResponse(BaseModel):
    """Response body for successful login or token refresh.

    The refresh credential is intentionally absent: it is delivered only as an
    HTTP-only cookie so client-side JavaScript can never read it
    (Requirement 3.5).
    """

    model_config = ConfigDict(extra="ignore")

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")


class MessageResponse(BaseModel):
    """Generic message response for operations like logout and password reset."""

    message: str = Field(..., description="Operation result message")


class PasswordResetResponse(BaseModel):
    """Generic response for password reset requests.

    The reset token is delivered through the configured notification queue and
    is intentionally never included in an API response.
    """

    message: str = Field(..., description="Informational message")


# =============================================================================
# Error Response Schemas
# =============================================================================


class ErrorDetail(BaseModel):
    """Structured error detail."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict | None = Field(default=None, description="Additional error context")


class ErrorResponse(BaseModel):
    """Standard API error response envelope."""

    error: ErrorDetail
