"""Pydantic schemas for authentication endpoints.

Defines request/response models for login, token refresh, logout,
and password reset operations.

Satisfies Requirements: 2.1, 2.2, 2.3, 2.4
"""

from pydantic import BaseModel, EmailStr, Field


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
    """Request body for POST /api/v1/auth/refresh."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Valid refresh token to exchange for new token pair",
    )


class LogoutRequest(BaseModel):
    """Request body for POST /api/v1/auth/logout."""

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
    """Response body for successful login or token refresh."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")


class MessageResponse(BaseModel):
    """Generic message response for operations like logout and password reset."""

    message: str = Field(..., description="Operation result message")


class PasswordResetResponse(BaseModel):
    """Response for password reset request (includes token for dev/testing)."""

    reset_token: str = Field(..., description="Password reset token")
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
