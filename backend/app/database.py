"""Async SQLAlchemy engine and session factory."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings
from app.migration_runner import run_migrations

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_async_engine(
    settings.async_database_url,
    echo=settings.database_echo,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session.

    Used as a FastAPI dependency for request-scoped sessions.
    The session is automatically closed after the request completes.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Prepare model metadata and optionally run controlled migrations.

    Schema creation and ad hoc DDL are intentionally not performed here.
    Deployments should run ``alembic upgrade head`` before serving traffic; an
    environment that enables ``run_migrations_on_startup`` fails closed when
    that operation raises.
    """
    _import_models()
    if settings.run_migrations_on_startup:
        await run_migrations(settings)
    else:
        logger.info(
            "database_migrations_skipped",
            extra={"reason": "deployment_step_required"},
        )


def _import_models() -> None:
    """Import all models to register them with Base.metadata."""
    import app.models  # noqa: F401


async def close_db() -> None:
    """Dispose of the database engine and connection pool."""
    await engine.dispose()
