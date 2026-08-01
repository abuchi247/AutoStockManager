"""Controlled Alembic migration execution for application deployments."""

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


_BACKEND_ROOT = Path(__file__).resolve().parent.parent


async def run_migrations(settings: Settings | None = None) -> None:
    """Upgrade the database to Alembic head and abort on any failure.

    The repository's ``alembic`` directory is also a Python package, so an
    in-process import of the installed Alembic package would be shadowed when
    the application runs from the backend directory. The installed Alembic
    executable avoids that collision and gives deployments the same command
    they can run independently.
    """
    effective_settings = settings or get_settings()
    alembic_executable = shutil.which("alembic")
    if alembic_executable is None:
        raise RuntimeError("Alembic executable is not installed")

    # Use the dedicated migration identity when configured (least-privilege
    # separation). Falls back to the application database URL otherwise.
    migration_url = (
        effective_settings.migration_database_url or effective_settings.database_url
    )
    environment = os.environ.copy()
    environment["DATABASE_URL"] = migration_url
    logger.info("database_migrations_started", extra={"migration_target": "head"})
    try:
        await asyncio.to_thread(
            subprocess.run,
            [alembic_executable, "upgrade", "head"],
            cwd=_BACKEND_ROOT,
            env=environment,
            check=True,
        )
    except Exception:
        logger.exception("database_migrations_failed")
        raise
    logger.info("database_migrations_completed", extra={"migration_target": "head"})
