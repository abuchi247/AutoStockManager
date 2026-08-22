"""Pydantic schemas for role permissions endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PermissionSet(BaseModel):
    """A single role's permissions."""

    role: str = Field(..., description="Role name")
    permissions: dict[str, bool] = Field(
        ..., description="Permission keys mapped to boolean values"
    )
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")


class RolePermissionsResponse(BaseModel):
    """Response for GET /api/v1/role-permissions."""

    roles: list[PermissionSet] = Field(
        ..., description="List of all roles with their permissions"
    )
    all_permissions: list[str] = Field(
        ..., description="Ordered list of all possible permission keys"
    )


class UpdateRolePermissionsRequest(BaseModel):
    """Request body for PUT /api/v1/role-permissions/{role}."""

    permissions: dict[str, bool] = Field(
        ..., description="Full permissions dict — all permission keys must be present"
    )


class UpdateRolePermissionsResponse(BaseModel):
    """Response for PUT /api/v1/role-permissions/{role}."""

    role: str
    permissions: dict[str, bool]
    updated_at: Optional[str] = None
    message: str = "Permissions updated successfully"
