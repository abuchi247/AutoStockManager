"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_async_session
from app.middleware.auth import get_current_user, require_roles  # noqa: F401
from app.models.user import User


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for request handlers.

    This is an alias for get_async_session for convenience.
    """
    async for session in get_async_session():
        yield session


# Type aliases for common dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
