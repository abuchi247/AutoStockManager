"""Unit tests for cache_service module.

Tests cover:
- Key construction with versioned namespaces
- Cache GET/SET/invalidate with TTL
- Family invalidation via pattern scan
- Graceful fallback when Redis is unavailable
- Identifier generation with parameter hashing
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.cache_service import (
    CACHE_FAMILIES,
    CACHE_VERSION,
    CacheService,
    _build_key,
    _hash_params,
)


# =============================================================================
# Key Construction Tests
# =============================================================================


class TestKeyConstruction:
    """Tests for cache key building with versioned namespaces."""

    def test_build_key_known_family(self):
        """Keys for known families use the configured prefix."""
        key = _build_key("dashboard_summary", "all")
        assert key == f"cache:{CACHE_VERSION}:dash:all"

    def test_build_key_categories(self):
        """Categories family uses 'cat' prefix."""
        key = _build_key("categories", "list")
        assert key == f"cache:{CACHE_VERSION}:cat:list"

    def test_build_key_unknown_family_uses_family_as_prefix(self):
        """Unknown families fall back to the family name as prefix."""
        key = _build_key("unknown_thing", "id123")
        assert key == f"cache:{CACHE_VERSION}:unknown_thing:id123"

    def test_build_key_includes_version(self):
        """All keys include the version namespace."""
        key = _build_key("locations", "active")
        assert f":{CACHE_VERSION}:" in key

    def test_hash_params_deterministic(self):
        """Same params produce the same hash."""
        params = {"page": 1, "limit": 20, "sort": "name"}
        h1 = _hash_params(params)
        h2 = _hash_params(params)
        assert h1 == h2

    def test_hash_params_different_for_different_input(self):
        """Different params produce different hashes."""
        h1 = _hash_params({"page": 1})
        h2 = _hash_params({"page": 2})
        assert h1 != h2

    def test_hash_params_order_independent(self):
        """Dict key order does not affect the hash (json sort_keys)."""
        h1 = _hash_params({"a": 1, "b": 2})
        h2 = _hash_params({"b": 2, "a": 1})
        assert h1 == h2


# =============================================================================
# CacheService with Mock Redis
# =============================================================================


class TestCacheServiceWithRedis:
    """Tests for CacheService operations with a mocked Redis client."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock async Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def cache(self, mock_redis):
        """Create a CacheService instance with mock Redis."""
        return CacheService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_get_returns_none_on_miss(self, cache, mock_redis):
        """Cache miss returns None."""
        mock_redis.get.return_value = None
        result = await cache.get("categories", "list")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_deserialized_value(self, cache, mock_redis):
        """Cache hit returns the deserialized JSON value."""
        stored = {"items": [{"id": 1, "name": "Brakes"}]}
        mock_redis.get.return_value = json.dumps(stored)
        result = await cache.get("categories", "list")
        assert result == stored

    @pytest.mark.asyncio
    async def test_set_stores_with_family_ttl(self, cache, mock_redis):
        """Set uses the family's default TTL when none is explicit."""
        data = {"total": 42}
        await cache.set("dashboard_summary", "all", data)
        mock_redis.set.assert_called_once()
        call_kwargs = mock_redis.set.call_args
        # Check that TTL matches dashboard_summary family (30s)
        assert call_kwargs.kwargs.get("ex") == 30 or call_kwargs[1].get("ex") == 30

    @pytest.mark.asyncio
    async def test_set_with_explicit_ttl(self, cache, mock_redis):
        """Explicit TTL overrides the family default."""
        data = {"total": 42}
        await cache.set("dashboard_summary", "all", data, ttl_seconds=10)
        call_kwargs = mock_redis.set.call_args
        assert call_kwargs.kwargs.get("ex") == 10 or call_kwargs[1].get("ex") == 10

    @pytest.mark.asyncio
    async def test_invalidate_deletes_key(self, cache, mock_redis):
        """Invalidate removes a specific cache entry."""
        await cache.invalidate("categories", "list")
        mock_redis.delete.assert_called_once()
        key_arg = mock_redis.delete.call_args[0][0]
        assert "cat:list" in key_arg

    @pytest.mark.asyncio
    async def test_invalidate_family_scans_and_deletes(self, cache, mock_redis):
        """Family invalidation scans matching keys and deletes them."""
        # Mock scan_iter to yield keys
        async def mock_scan_iter(match=None, count=None):
            for k in [b"cache:v1:cat:list", b"cache:v1:cat:detail:123"]:
                yield k

        mock_redis.scan_iter = mock_scan_iter
        deleted = await cache.invalidate_family("categories")
        assert deleted == 2
        assert mock_redis.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_available_property_true_with_redis(self, cache):
        """available is True when a Redis client is provided."""
        assert cache.available is True


# =============================================================================
# CacheService Without Redis (Graceful Fallback)
# =============================================================================


class TestCacheServiceFallback:
    """Tests for CacheService behavior when Redis is unavailable."""

    @pytest.fixture
    def cache_no_redis(self):
        """CacheService with no Redis client (unavailable)."""
        return CacheService(redis_client=None)

    def test_available_property_false(self, cache_no_redis):
        """available is False when Redis is None."""
        assert cache_no_redis.available is False

    @pytest.mark.asyncio
    async def test_get_returns_none(self, cache_no_redis):
        """GET returns None when Redis is unavailable."""
        result = await cache_no_redis.get("categories", "list")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_does_not_raise(self, cache_no_redis):
        """SET completes silently when Redis is unavailable."""
        await cache_no_redis.set("categories", "list", {"items": []})

    @pytest.mark.asyncio
    async def test_invalidate_does_not_raise(self, cache_no_redis):
        """Invalidate completes silently when Redis is unavailable."""
        await cache_no_redis.invalidate("categories", "list")

    @pytest.mark.asyncio
    async def test_invalidate_family_returns_zero(self, cache_no_redis):
        """Family invalidation returns 0 when Redis is unavailable."""
        result = await cache_no_redis.invalidate_family("categories")
        assert result == 0


# =============================================================================
# CacheService Error Handling
# =============================================================================


class TestCacheServiceErrorHandling:
    """Tests for CacheService graceful error handling on Redis failures."""

    @pytest.fixture
    def broken_redis(self):
        """Redis client that raises exceptions on every call."""
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        redis.delete = AsyncMock(side_effect=ConnectionError("Redis down"))
        return redis

    @pytest.fixture
    def cache(self, broken_redis):
        return CacheService(redis_client=broken_redis)

    @pytest.mark.asyncio
    async def test_get_returns_none_on_error(self, cache):
        """GET returns None when Redis raises."""
        result = await cache.get("categories", "list")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_does_not_raise_on_error(self, cache):
        """SET completes silently when Redis raises."""
        await cache.set("categories", "list", {"items": []})

    @pytest.mark.asyncio
    async def test_invalidate_does_not_raise_on_error(self, cache):
        """Invalidate completes silently when Redis raises."""
        await cache.invalidate("categories", "list")


# =============================================================================
# Identifier Generation
# =============================================================================


class TestMakeIdentifier:
    """Tests for CacheService.make_identifier helper."""

    def test_without_params(self):
        """Returns the base string when no params given."""
        assert CacheService.make_identifier("all") == "all"

    def test_with_params(self):
        """Returns base:hash when params are provided."""
        ident = CacheService.make_identifier("list", {"page": 1, "limit": 20})
        assert ident.startswith("list:")
        assert len(ident) > len("list:")

    def test_same_params_same_identifier(self):
        """Same params produce the same identifier."""
        i1 = CacheService.make_identifier("list", {"page": 1})
        i2 = CacheService.make_identifier("list", {"page": 1})
        assert i1 == i2

    def test_different_params_different_identifier(self):
        """Different params produce different identifiers."""
        i1 = CacheService.make_identifier("list", {"page": 1})
        i2 = CacheService.make_identifier("list", {"page": 2})
        assert i1 != i2


# =============================================================================
# Cache Families Configuration
# =============================================================================


class TestCacheFamilies:
    """Tests for cache family configuration."""

    def test_dashboard_summary_ttl(self):
        """Dashboard summary has a short TTL (30s)."""
        prefix, ttl = CACHE_FAMILIES["dashboard_summary"]
        assert ttl == 30
        assert prefix == "dash"

    def test_categories_ttl(self):
        """Categories have a longer TTL (300s) since they rarely change."""
        prefix, ttl = CACHE_FAMILIES["categories"]
        assert ttl == 300
        assert prefix == "cat"

    def test_locations_ttl(self):
        """Locations have a longer TTL (300s)."""
        prefix, ttl = CACHE_FAMILIES["locations"]
        assert ttl == 300
        assert prefix == "loc"

    def test_all_families_have_prefix_and_ttl(self):
        """Every defined family has both a prefix and a TTL."""
        for name, (prefix, ttl) in CACHE_FAMILIES.items():
            assert isinstance(prefix, str) and len(prefix) > 0
            assert isinstance(ttl, int) and ttl > 0
