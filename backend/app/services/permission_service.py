"""
Permission service for configurable role-based access control.

Provides:
- check_permission(db, role, permission_key) → bool
- get_all_role_permissions(db) → dict
- update_role_permissions(db, role, permissions, updated_by) → RolePermission

The Admin role ALWAYS has all permissions regardless of what's stored in
the database. This is enforced in check_permission() so that an Admin
can never accidentally lock themselves out.

Permissions are cached per-request via the SQLAlchemy session identity map.
For cross-request caching, use a short-lived in-memory TTL cache (60s)
since permission changes are rare and a 60s propagation delay is acceptable.
"""

import logging
from functools import lru_cache
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role_permission import RolePermission

logger = logging.getLogger(__name__)

# In-memory cache: role → permissions dict. Cleared on update.
_permissions_cache: dict[str, dict[str, bool]] = {}


def invalidate_permissions_cache() -> None:
    """Clear the in-memory permissions cache after an update."""
    _permissions_cache.clear()


async def _load_role_permissions(db: AsyncSession, role: str) -> dict[str, bool]:
    """Load permissions for a role from DB, using the in-memory cache."""
    if role in _permissions_cache:
        return _permissions_cache[role]

    result = await db.execute(
        select(RolePermission).filter(RolePermission.role == role)
    )
    rp = result.scalar_one_or_none()

    if rp is None:
        # Role not found — default to empty (no permissions)
        _permissions_cache[role] = {}
        return {}

    perms = rp.permissions if isinstance(rp.permissions, dict) else {}
    _permissions_cache[role] = perms
    return perms


async def check_permission(
    db: AsyncSession,
    role: str,
    permission_key: str,
) -> bool:
    """Check if a role has a specific permission.

    Admin always returns True. For other roles, checks the configurable
    permissions in the database.

    Args:
        db: Async database session.
        role: The user's role (e.g. "Admin", "Manager", "Salesperson", "Storekeeper").
        permission_key: The permission to check (e.g. "process_returns").

    Returns:
        True if the role has the permission, False otherwise.
    """
    # Admin always has all permissions — cannot be locked out
    if role == "Admin":
        return True

    perms = await _load_role_permissions(db, role)
    return perms.get(permission_key, False)


async def get_all_role_permissions(db: AsyncSession) -> list[dict]:
    """Get all role permissions for the admin UI.

    Returns:
        List of dicts with 'role' and 'permissions' keys.
    """
    result = await db.execute(
        select(RolePermission).order_by(RolePermission.role)
    )
    rows = result.scalars().all()

    return [
        {
            "role": rp.role,
            "permissions": rp.permissions if isinstance(rp.permissions, dict) else {},
            "updated_at": rp.updated_at.isoformat() if rp.updated_at else None,
        }
        for rp in rows
    ]


async def update_role_permissions(
    db: AsyncSession,
    role: str,
    permissions: dict[str, bool],
    updated_by: Optional[str] = None,
) -> RolePermission:
    """Update permissions for a specific role.

    Args:
        db: Async database session.
        role: The role to update.
        permissions: Full permissions dict (all keys must be present).
        updated_by: UUID of the admin making the change.

    Returns:
        The updated RolePermission object.

    Raises:
        ValueError: If the role is "Admin" (cannot modify Admin permissions).
        ValueError: If the role doesn't exist.
    """
    if role == "Admin":
        raise ValueError("Admin permissions cannot be modified — Admin always has full access.")

    result = await db.execute(
        select(RolePermission).filter(RolePermission.role == role)
    )
    rp = result.scalar_one_or_none()

    if rp is None:
        raise ValueError(f"Role '{role}' not found in role_permissions table.")

    rp.permissions = permissions
    rp.updated_by = updated_by
    await db.flush()

    # Invalidate cache so the new permissions take effect immediately
    invalidate_permissions_cache()

    return rp


# ---------------------------------------------------------------------------
# FastAPI dependency factory for declarative permission checks
# ---------------------------------------------------------------------------

from fastapi import Depends, HTTPException, status as http_status
from app.dependencies import CurrentUser, DbSession


def require_permission(permission_key: str):
    """FastAPI dependency that checks a configurable permission.

    Usage:
        @router.post("/...", dependencies=[Depends(require_permission("process_returns"))])
        async def my_endpoint(...):
            ...

    Or to get the user back:
        async def my_endpoint(
            current_user: User = Depends(require_permission("process_returns"))
        ):
            ...
    """
    async def _checker(
        db: DbSession,
        current_user: CurrentUser,
    ):
        has_perm = await check_permission(db, current_user.role, permission_key)
        if not has_perm:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission_key}' is not enabled for your role. Contact your Admin.",
            )
        return current_user

    return _checker
