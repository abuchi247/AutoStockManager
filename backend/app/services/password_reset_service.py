"""Password-reset notification queue contract backed by ARQ and Redis."""

from typing import Any, Protocol

import redis.asyncio as aioredis

from app.config import Settings, get_settings
from app.services.background_jobs import enqueue_job


class PasswordResetJobQueue(Protocol):
    """Queue contract used by authentication without coupling to a worker."""

    async def enqueue(self, job_name: str, payload: dict[str, Any]) -> str:
        """Enqueue a job and return its opaque identifier."""
        ...


class RedisPasswordResetJobQueue:
    """ARQ adapter for password-reset delivery.

    ``redis_client`` remains accepted for compatibility with the auth service's
    dependency wiring. ARQ owns its worker-compatible connection pool so the
    request path uses the same Redis deployment and queue namespace as workers.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.redis = redis_client
        self.settings = settings or get_settings()

    async def enqueue(self, job_name: str, payload: dict[str, Any]) -> str:
        return await enqueue_job(job_name, payload, self.settings)
