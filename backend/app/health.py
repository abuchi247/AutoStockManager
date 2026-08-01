"""Dependency-aware health checks for the application readiness endpoint."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import text


async def _check_database(database_engine: Any) -> None:
    """Run a minimal query using the application's shared database engine."""
    async with database_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _check_redis(redis_client: Any) -> None:
    """Run a connectivity check using the application's shared Redis client."""
    await redis_client.ping()


async def _bounded_check(
    check: Callable[[], Awaitable[Any]],
    timeout_seconds: float,
) -> str:
    """Return a safe status while bounding failures and dependency hangs."""
    try:
        await asyncio.wait_for(check(), timeout=timeout_seconds)
    except Exception:
        # Health responses intentionally expose only availability, never the
        # dependency exception, credentials, or an internal traceback.
        return "down"
    return "up"


async def check_dependencies(
    database_engine: Any,
    redis_client: Any,
    timeout_seconds: float = 2.0,
) -> dict[str, str]:
    """Check PostgreSQL and Redis concurrently with an independent timeout."""
    timeout_seconds = max(0.001, timeout_seconds)

    async def check_database() -> None:
        await _check_database(database_engine)

    async def check_redis() -> None:
        if redis_client is None:
            raise RuntimeError("Redis client unavailable")
        await _check_redis(redis_client)

    database_status, redis_status = await asyncio.gather(
        _bounded_check(check_database, timeout_seconds),
        _bounded_check(check_redis, timeout_seconds),
    )
    return {"database": database_status, "redis": redis_status}
