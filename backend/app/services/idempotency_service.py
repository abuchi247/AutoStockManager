"""Idempotency key service for non-idempotent operations.

Prevents duplicate side effects when clients retry requests that create sales,
stock movements, emails, or other irreversible operations.

Protocol:
1. Client sends a unique Idempotency-Key header with a non-idempotent request.
2. Service checks if the key has been seen before (scoped to actor + operation).
3. If unseen: execute the operation, store the response with TTL, return it.
4. If seen with identical request body hash: return the stored response (valid retry).
5. If seen with different body hash: return 422 (body consistency violation).

Keys are stored in Redis with a bounded TTL (default 24 hours) to cover
reasonable client retry windows without accumulating indefinitely.
"""

from __future__ import annotations

import hashlib
import json
import logging
from enum import Enum
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# How long to retain idempotency results (seconds). 24h covers retries.
DEFAULT_IDEMPOTENCY_TTL_SECONDS = 86400

IDEMPOTENCY_KEY_PREFIX = "idem:v1"


class IdempotencyStatus(str, Enum):
    """Possible outcomes of an idempotency check."""

    NEW = "new"
    HIT = "hit"
    CONFLICT = "conflict"
    IN_PROGRESS = "in_progress"


class IdempotencyResult:
    """Result of checking an idempotency key."""

    def __init__(
        self,
        status: IdempotencyStatus,
        stored_response: Optional[dict[str, Any]] = None,
        stored_status_code: Optional[int] = None,
    ) -> None:
        self.status = status
        self.stored_response = stored_response
        self.stored_status_code = stored_status_code


def _compute_body_hash(body: bytes | str | dict[str, Any]) -> str:
    """Compute a SHA-256 hash of the request body for consistency checks."""
    if isinstance(body, dict):
        raw = json.dumps(body, sort_keys=True, default=str).encode()
    elif isinstance(body, str):
        raw = body.encode()
    else:
        raw = body
    return hashlib.sha256(raw).hexdigest()


def _build_idem_key(actor_id: str, operation: str, idempotency_key: str) -> str:
    """Build the Redis key for an idempotency entry.

    Scoped to actor + operation so different users/operations can't collide.
    """
    return f"{IDEMPOTENCY_KEY_PREFIX}:{operation}:{actor_id}:{idempotency_key}"


class IdempotencyService:
    """Service providing idempotency-key deduplication via Redis.

    Thread-safe for concurrent use within a single process — Redis SET NX
    provides atomicity for the claim step.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        ttl_seconds: int = DEFAULT_IDEMPOTENCY_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    async def check(
        self,
        *,
        actor_id: str,
        operation: str,
        idempotency_key: str,
        request_body: bytes | str | dict[str, Any],
    ) -> IdempotencyResult:
        """Check whether an idempotency key has already been used.

        Returns:
            IdempotencyResult indicating whether this is a new request,
            a valid retry (hit), or a body-mismatch conflict.
        """
        redis_key = _build_idem_key(actor_id, operation, idempotency_key)
        body_hash = _compute_body_hash(request_body)

        try:
            existing = await self._redis.get(redis_key)
        except Exception:
            logger.warning("idempotency_redis_error", extra={"key": redis_key})
            # Fail open: treat as new to avoid blocking the operation.
            return IdempotencyResult(status=IdempotencyStatus.NEW)

        if existing is None:
            # Try to atomically claim the key with NX.
            # Store a "processing" marker so concurrent duplicate requests
            # know the operation is in flight.
            marker = json.dumps({"body_hash": body_hash, "state": "processing"})
            claimed = await self._redis.set(
                redis_key, marker, ex=self._ttl, nx=True
            )
            if claimed:
                return IdempotencyResult(status=IdempotencyStatus.NEW)
            # Lost the race — another request claimed it. Re-read.
            existing = await self._redis.get(redis_key)
            if existing is None:
                # Vanished between attempts (rare); treat as new.
                return IdempotencyResult(status=IdempotencyStatus.NEW)

        # Key exists — parse it.
        try:
            data = json.loads(existing)
        except (json.JSONDecodeError, TypeError):
            # Corrupted entry; overwrite and treat as new.
            return IdempotencyResult(status=IdempotencyStatus.NEW)

        stored_hash = data.get("body_hash", "")

        # Body consistency check.
        if stored_hash != body_hash:
            return IdempotencyResult(status=IdempotencyStatus.CONFLICT)

        # If still processing, tell caller to wait or retry later.
        if data.get("state") == "processing":
            return IdempotencyResult(status=IdempotencyStatus.IN_PROGRESS)

        # Valid retry — return stored response.
        return IdempotencyResult(
            status=IdempotencyStatus.HIT,
            stored_response=data.get("response"),
            stored_status_code=data.get("status_code"),
        )

    async def store_response(
        self,
        *,
        actor_id: str,
        operation: str,
        idempotency_key: str,
        request_body: bytes | str | dict[str, Any],
        response_body: dict[str, Any],
        status_code: int,
    ) -> None:
        """Store the operation result so retries return the original response."""
        redis_key = _build_idem_key(actor_id, operation, idempotency_key)
        body_hash = _compute_body_hash(request_body)

        entry = json.dumps(
            {
                "body_hash": body_hash,
                "state": "complete",
                "response": response_body,
                "status_code": status_code,
            },
            default=str,
        )
        try:
            await self._redis.set(redis_key, entry, ex=self._ttl)
        except Exception:
            logger.warning(
                "idempotency_store_error", extra={"key": redis_key}
            )

    async def clear(
        self,
        *,
        actor_id: str,
        operation: str,
        idempotency_key: str,
    ) -> None:
        """Remove an idempotency marker (e.g. on operation failure)."""
        redis_key = _build_idem_key(actor_id, operation, idempotency_key)
        try:
            await self._redis.delete(redis_key)
        except Exception:
            pass


class JobDeduplicator:
    """Deduplication for background jobs keyed by a stable job identity.

    Prevents duplicate job execution when a worker retries or the same job
    is accidentally enqueued twice.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        ttl_seconds: int = DEFAULT_IDEMPOTENCY_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    async def try_claim(self, job_key: str) -> bool:
        """Atomically claim a job deduplication slot.

        Returns True if this caller won the claim (should execute),
        False if the job has already been claimed (duplicate).
        """
        redis_key = f"{IDEMPOTENCY_KEY_PREFIX}:job:{job_key}"
        try:
            return bool(await self._redis.set(redis_key, "1", ex=self._ttl, nx=True))
        except Exception:
            logger.warning("job_dedup_error", extra={"job_key": job_key})
            # Fail open so jobs aren't permanently blocked.
            return True

    async def release(self, job_key: str) -> None:
        """Release a job claim (e.g. on unrecoverable failure)."""
        redis_key = f"{IDEMPOTENCY_KEY_PREFIX}:job:{job_key}"
        try:
            await self._redis.delete(redis_key)
        except Exception:
            pass

    async def is_claimed(self, job_key: str) -> bool:
        """Check if a job key has already been claimed."""
        redis_key = f"{IDEMPOTENCY_KEY_PREFIX}:job:{job_key}"
        try:
            return bool(await self._redis.exists(redis_key))
        except Exception:
            return False
