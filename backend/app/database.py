"""Async SQLAlchemy engine and session factory."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

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
    """Initialize database: create all tables and required sequences.

    Uses CREATE TABLE IF NOT EXISTS semantics — safe to run on every startup.
    This ensures Railway deployments always have the latest schema without
    manual intervention.
    """
    # Import all models so Base.metadata knows about them
    _import_models()

    try:
        async with engine.begin() as conn:
            # Create all tables that don't exist yet
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables synced (create_all)")

            # Create invoice number sequence if it doesn't exist
            await conn.execute(
                text("CREATE SEQUENCE IF NOT EXISTS invoice_number_seq START 1")
            )
            logger.info("invoice_number_seq sequence ensured")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Don't crash the app — let it start and retry connections later
        # This prevents Railway from killing the container during deploy


def _import_models() -> None:
    """Import all models to register them with Base.metadata."""
    import app.models  # noqa: F401


async def close_db() -> None:
    """Dispose of the database engine and connection pool."""
    await engine.dispose()
