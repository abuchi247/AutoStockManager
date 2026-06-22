"""JWT authentication middleware and role-based access control dependencies.

Provides FastAPI dependencies for:
- Extracting and validating JWT access tokens from Authorization headers
- Enforcing role-based access control on API endpoints

Satisfies Requirements:
- 17.1: Enforce role-based access control on every API endpoint
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_async_session
from app.models.user import User, UserRole

security_scheme = HTTPBearer(auto_error=False)


async def _get_db():
    """Provide an async database session."""
    async for session in get_async_session():
        yield session


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security_scheme)
    ],
    db: Annotated[AsyncSession, Depends(_get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Extract and validate the current user from the JWT access token.

    Decodes the Bearer token from the Authorization header, verifies the
    signature, extracts user_id and role, then loads the User from the database.

    Returns the User ORM object associated with the token subject.

    Raises:
        HTTPException 401: If the token is missing, expired, or invalid.
        HTTPException 403: If the user account is inactive.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Only accept access tokens (not refresh or reset tokens)
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).filter_by(id=user_id, deleted_at=None))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def require_roles(*roles: UserRole):
    """Dependency factory that enforces role-based access control.

    Creates a FastAPI dependency that checks whether the authenticated user's
    role is among the allowed roles for the endpoint.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_roles(UserRole.ADMIN))])
        async def admin_endpoint():
            ...

        @router.get("/managers")
        async def manager_endpoint(
            user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
        ):
            ...

    Args:
        *roles: One or more UserRole enum values that are permitted access.

    Returns:
        A FastAPI dependency function that validates the user's role.

    Raises:
        HTTPException 403: If the user's role is not in the allowed roles.
    """
    allowed_roles = set(r.value if isinstance(r, UserRole) else r for r in roles)

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        """Check that the current user's role is in the allowed set."""
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker
