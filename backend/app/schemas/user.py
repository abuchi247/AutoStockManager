"""Pydantic schemas for user management endpoints.

Defines request/response models for user CRUD operations (Admin only).

Satisfies Requirements: 2.1, 2.5
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


# =============================================================================
# Request Schemas
# =============================================================================


class UserCreate(BaseModel):
    """Request body for POST /api/v1/users (create new user)."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=150,
        description="Unique login username",
        examples=["john_doe"],
    )
    email: EmailStr = Field(
        ...,
        description="Unique email address",
        examples=["john@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password (min 8 chars, must include uppercase, lowercase, and digit)",
        examples=["SecurePass1"],
    )
    role: UserRole = Field(
        ...,
        description="User role assignment",
        examples=["Salesperson"],
    )
    is_active: bool = Field(
        default=True,
        description="Whether the account is active on creation",
    )


class UserUpdate(BaseModel):
    """Request body for updating a user (partial update)."""

    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=150,
        description="New username",
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="New email address",
    )
    role: Optional[UserRole] = Field(
        default=None,
        description="New role assignment",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Enable or disable the account",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class UserResponse(BaseModel):
    """Response body for a single user."""

    id: UUID = Field(..., description="User unique identifier")
    username: str = Field(..., description="Login username")
    email: str = Field(..., description="Email address")
    role: str = Field(..., description="User role")
    is_active: bool = Field(..., description="Whether the account is active")
    failed_login_attempts: int = Field(..., description="Number of consecutive failed login attempts")
    locked_until: Optional[datetime] = Field(
        default=None,
        description="Account locked until this timestamp (null if not locked)",
    )
    created_at: Optional[datetime] = Field(default=None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Response body for user list with pagination metadata."""

    data: list[UserResponse] = Field(..., description="List of users")
    meta: dict = Field(
        default_factory=lambda: {"page": 1, "total": 0},
        description="Pagination metadata",
    )
