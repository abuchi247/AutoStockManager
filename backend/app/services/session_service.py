"""
Session registry and login history service.

Manages active user sessions via Redis and records login history to PostgreSQL.

Satisfies Requirements:
- 17.3: Maintain session registry tracking all active refresh tokens per user
- 17.4: On logout, invalidate the refresh token and remove from session registry
- 17.5: Record login history (timestamp, IP, user agent, success/failure)
- 17.6: Admin session revocation - invalidate all refresh tokens for a user
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.login_history import LoginHistory


# Redis key patterns for session registry
SESSION_REGISTRY_PREFIX = "session:user:"
SESSION_TOKEN_PREFIX = "session:token:"


class SessionService:
    """Service managing user sessions in Redis and login history in PostgreSQL.

    Session Registry (Redis):
    - Each user has a Redis SET at key "session:user:{user_id}" containing
      all active refresh token JTIs (JWT IDs).
    - Each token JTI has a Redis key "session:token:{jti}" storing session
      metadata (user_id, ip_address, user_agent, created_at).
    - Token entries auto-expire based on the refresh token TTL.

    Login History (PostgreSQL):
    - Every login attempt (success or failure) is recorded in the
      login_history table with contextual information.

    Admin Revocation:
    - Revoking all sessions for a user removes the user's session SET
      and all individual token entries from Redis, effectively invalidating
      all refresh tokens.
    """

    def __init__(
        self,
        db: AsyncSession,
        redis_client: aioredis.Redis,
        settings: Optional[Settings] = None,
    ):
        """Initialize the session service.

        Args:
            db: Async SQLAlchemy session for login history persistence.
            redis_client: Async Redis client for session registry.
            settings: Application settings (defaults to singleton).
        """
        self.db = db
        self.redis = redis_client
        self.settings = settings or get_settings()

    # =========================================================================
    # Session Registry (Redis)
    # =========================================================================

    async def register_session(
        self,
        user_id: str,
        jti: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Register a new refresh token session in Redis.

        Adds the token's JTI to the user's session set and stores
        session metadata for the token.

        Args:
            user_id: The user's UUID string.
            jti: The refresh token's unique JWT ID.
            ip_address: Client IP address.
            user_agent: Client user agent string.
        """
        # TTL matches refresh token expiry
        ttl_seconds = self.settings.jwt_refresh_token_expire_days * 86400

        # Add JTI to user's session set
        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"
        await self.redis.sadd(user_key, jti)
        await self.redis.expire(user_key, ttl_seconds)

        # Store session metadata
        token_key = f"{SESSION_TOKEN_PREFIX}{jti}"
        session_data = {
            "user_id": user_id,
            "jti": jti,
            "ip_address": ip_address or "",
            "user_agent": user_agent or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.redis.set(token_key, json.dumps(session_data), ex=ttl_seconds)

    async def is_session_valid(self, user_id: str, jti: str) -> bool:
        """Check if a refresh token JTI is still registered (not revoked).

        Args:
            user_id: The user's UUID string.
            jti: The refresh token's JWT ID to check.

        Returns:
            True if the session is active, False if revoked or expired.
        """
        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"
        return await self.redis.sismember(user_key, jti)

    async def remove_session(self, user_id: str, jti: str) -> None:
        """Remove a single session (logout) from the registry.

        Removes the token's JTI from the user's session set and deletes
        the associated session metadata.

        Args:
            user_id: The user's UUID string.
            jti: The refresh token's JWT ID to remove.
        """
        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"
        token_key = f"{SESSION_TOKEN_PREFIX}{jti}"

        await self.redis.srem(user_key, jti)
        await self.redis.delete(token_key)

    async def revoke_all_sessions(self, user_id: str) -> int:
        """Revoke all active sessions for a user (admin action).

        Removes all refresh token JTIs from the user's session set and
        deletes all associated session metadata keys.

        Args:
            user_id: The user's UUID string.

        Returns:
            The number of sessions that were revoked.
        """
        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"

        # Get all active JTIs for the user
        jtis = await self.redis.smembers(user_key)
        revoked_count = len(jtis)

        if jtis:
            # Delete all token metadata keys
            token_keys = [f"{SESSION_TOKEN_PREFIX}{jti}" for jti in jtis]
            await self.redis.delete(*token_keys)

        # Delete the user's session set
        await self.redis.delete(user_key)

        return revoked_count

    async def get_active_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Get all active sessions for a user.

        Retrieves session metadata for all active refresh tokens.

        Args:
            user_id: The user's UUID string.

        Returns:
            List of session metadata dictionaries.
        """
        user_key = f"{SESSION_REGISTRY_PREFIX}{user_id}"
        jtis = await self.redis.smembers(user_key)

        sessions = []
        for jti in jtis:
            token_key = f"{SESSION_TOKEN_PREFIX}{jti}"
            data = await self.redis.get(token_key)
            if data:
                sessions.append(json.loads(data))
            else:
                # Token metadata expired but JTI still in set; clean up
                await self.redis.srem(user_key, jti)

        return sessions

    # =========================================================================
    # Login History (PostgreSQL)
    # =========================================================================

    async def record_login_attempt(
        self,
        username: str,
        success: bool,
        user_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> LoginHistory:
        """Record a login attempt in the login history table.

        Creates an append-only record of the authentication attempt
        with all contextual information.

        Args:
            username: The username used in the attempt.
            success: Whether the login was successful.
            user_id: The user's UUID (if user was found).
            ip_address: Client IP address.
            user_agent: Client user agent string.
            failure_reason: Reason for failure (if applicable).

        Returns:
            The created LoginHistory record.
        """
        record = LoginHistory(
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_login_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[LoginHistory]:
        """Get login history for a specific user.

        Args:
            user_id: The user's UUID.
            limit: Maximum number of records to return.

        Returns:
            List of LoginHistory records ordered by most recent first.
        """
        from sqlalchemy import select

        stmt = (
            select(LoginHistory)
            .filter_by(user_id=user_id)
            .order_by(LoginHistory.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


# =============================================================================
# Redis Connection Factory
# =============================================================================

_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """Get or create a shared async Redis client.

    Returns:
        Async Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close the Redis client connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
