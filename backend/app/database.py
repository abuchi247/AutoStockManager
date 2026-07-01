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
    """Initialize database: run Alembic migrations and create sequences.

    Runs Alembic migrations on startup (upgrade to head) to handle both
    new table creation and column additions on existing tables.
    This ensures Railway deployments always have the latest schema.
    """
    # Import all models so Base.metadata knows about them
    _import_models()

    try:
        # Run Alembic migrations to handle schema changes (ADD COLUMN, etc.)
        import asyncio
        from alembic.config import Config
        from alembic import command
        import os

        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
        alembic_cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "..", "alembic"))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, command.upgrade, alembic_cfg, "head")
        logger.info("Alembic migrations applied (upgrade head)")

        async with engine.begin() as conn:
            # Create invoice number sequence if it doesn't exist
            await conn.execute(
                text("CREATE SEQUENCE IF NOT EXISTS invoice_number_seq START 1")
            )
            logger.info("invoice_number_seq sequence ensured")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Fallback: try create_all for new tables at minimum
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Fallback: Database tables synced (create_all)")
        except Exception as e2:
            logger.error(f"Fallback init also failed: {e2}")
        # Don't crash the app — let it start and retry connections later


def _import_models() -> None:
    """Import all models to register them with Base.metadata."""
    import app.models  # noqa: F401


async def close_db() -> None:
    """Dispose of the database engine and connection pool."""
    await engine.dispose()
