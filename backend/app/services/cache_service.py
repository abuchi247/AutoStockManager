"""Cache-aside read service with versioned key namespaces and TTL management.

Design principles:
- Redis is an optimization, NOT the source of truth for financial/inventory data.
- Namespaces include resource type and version for safe rolling deployments.
- TTL and invalidation are explicit per cache family.
- Fallback to database is always available when Redis is unavailable.

Cacheable reads (safe, non-sensitive):
- Dashboard summary statistics (TTL: 30s)
- Category lists (TTL: 300s, rarely change)
- Location lists (TTL: 300s, rarely change)
- Spare part catalog lookups (TTL: 60s)

NOT cacheable (sensitive or rapidly changing):
- User sessions, credentials, tokens
- Stock quantities (source of truth is the ledger/cache table)
- Sales/purchase financial data
- Audit trails
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Namespace version: bump when cache structure changes to avoid stale reads.
CACHE_VERSION = "v1"

# Cache family definitions: (prefix, default_ttl_seconds)
CACHE_FAMILIES = {
    "dashboard_summary": ("dash", 30),
    "categories": ("cat", 300),
    "locations": ("loc", 300),
    "spare_parts_list": ("sp_list", 60),
    "spare_part_detail": ("sp_det", 60),
    "business_settings": ("biz_set", 120),
}


def _build_key(family: str, identifier: str) -> str:
    """Build a namespaced cache key.

    Format: cache:{version}:{family_prefix}:{identifier}
    """
    prefix = CACHE_FAMILIES.get(family, (family, 60))[0]
    return f"cache:{CACHE_VERSION}:{prefix}:{identifier}"


def _hash_params(params: dict[str, Any]) -> str:
    """Create a deterministic short hash of query parameters for cache keys."""
    serialized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


class CacheService:
    """Cache-aside service wrapping Redis GET/SET with namespace and TTL.

    Falls back gracefully when Redis is unavailable — callers always receive
    None on cache miss or error, and must query the source of truth.
    """

    def __init__(self, redis_client: Optional[aioredis.Redis] = None) -> None:
        self._redis = redis_client

    @property
    def available(self) -> bool:
        return self._redis is not None

    async def get(self, family: str, identifier: str) -> Optional[Any]:
        """Retrieve a cached value. Returns None on miss or error."""
        if not self._redis:
            return None
        key = _build_key(family, identifier)
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.debug("cache_get_error", extra={"key": key})
            return None

    async def set(
        self,
        family: str,
        identifier: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store a value in the cache with the family's default or explicit TTL."""
        if not self._redis:
            return
        key = _build_key(family, identifier)
        if ttl_seconds is None:
            ttl_seconds = CACHE_FAMILIES.get(family, (family, 60))[1]
        try:
            serialized = json.dumps(value, default=str)
            await self._redis.set(key, serialized, ex=ttl_seconds)
        except Exception:
            logger.debug("cache_set_error", extra={"key": key})

    async def invalidate(self, family: str, identifier: str) -> None:
        """Remove a single entry from the cache."""
        if not self._redis:
            return
        key = _build_key(family, identifier)
        try:
            await self._redis.delete(key)
        except Exception:
            logger.debug("cache_invalidate_error", extra={"key": key})

    async def invalidate_family(self, family: str) -> int:
        """Invalidate all keys in a cache family using SCAN (non-blocking).

        Returns the number of keys deleted, or 0 if Redis is unavailable.
        """
        if not self._redis:
            return 0
        prefix = CACHE_FAMILIES.get(family, (family, 60))[0]
        pattern = f"cache:{CACHE_VERSION}:{prefix}:*"
        deleted = 0
        try:
            async for key in self._redis.scan_iter(match=pattern, count=100):
                await self._redis.delete(key)
                deleted += 1
        except Exception:
            logger.debug("cache_invalidate_family_error", extra={"family": family})
        return deleted

    @staticmethod
    def make_identifier(base: str, params: Optional[dict[str, Any]] = None) -> str:
        """Build a cache identifier from a base string and optional params."""
        if not params:
            return base
        return f"{base}:{_hash_params(params)}"
