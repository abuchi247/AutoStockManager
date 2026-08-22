"""Role permissions management router.

Provides:
- GET  /api/v1/role-permissions          - Get all roles and their permissions (Admin only)
- PUT  /api/v1/role-permissions/{role}   - Update permissions for a role (Admin only)

These endpoints allow the Admin to configure which permissions each role
has via a checkbox matrix in the Settings UI.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import CurrentUser, DbSession
from app.middleware.auth import require_roles
from app.models.user import User, UserRole
from app.initial_data import ALL_PERMISSIONS
from app.schemas.role_permission import (
    PermissionSet,
    RolePermissionsResponse,
    UpdateRolePermissionsRequest,
    UpdateRolePermissionsResponse,
)
from app.services.permission_service import (
    get_all_role_permissions,
    update_role_permissions,
)

router = APIRouter(prefix="/api/v1/role-permissions", tags=["Role Permissions"])


@router.get(
    "",
    response_model=RolePermissionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all role permissions",
    description="Retrieve the full permissions matrix for all roles. Admin only.",
)
async def get_permissions(
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> RolePermissionsResponse:
    """Return all roles with their current permission assignments."""
    roles_data = await get_all_role_permissions(db)

    return RolePermissionsResponse(
        roles=[
            PermissionSet(
                role=r["role"],
                permissions=r["permissions"],
                updated_at=r["updated_at"],
            )
            for r in roles_data
        ],
        all_permissions=ALL_PERMISSIONS,
    )


@router.put(
    "/{role}",
    response_model=UpdateRolePermissionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update role permissions",
    description="Update the permissions for a specific role. Admin only. Cannot modify Admin role.",
    responses={
        400: {"description": "Cannot modify Admin role or role not found"},
        403: {"description": "Insufficient permissions"},
    },
)
async def update_permissions(
    role: str,
    request: UpdateRolePermissionsRequest,
    db: DbSession,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> UpdateRolePermissionsResponse:
    """Update permissions for a role.

    The request body must contain ALL permission keys with boolean values.
    Admin permissions cannot be modified.
    """
    try:
        rp = await update_role_permissions(
            db=db,
            role=role,
            permissions=request.permissions,
            updated_by=str(current_user.id),
        )
        await db.commit()
        await db.refresh(rp)

        return UpdateRolePermissionsResponse(
            role=rp.role,
            permissions=rp.permissions,
            updated_at=rp.updated_at.isoformat() if rp.updated_at else None,
            message=f"Permissions for '{role}' updated successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
