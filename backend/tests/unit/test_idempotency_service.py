"""Unit tests for idempotency_service module.

Tests cover:
- New request claim via SET NX
- Valid retry returns stored response (idempotency hit)
- Body consistency enforcement (conflict on body mismatch)
- In-progress marker for concurrent duplicate requests
- Response storage after successful operation
- Job deduplication (try_claim, release, is_claimed)
- Concurrency tests proving duplicate requests do not duplicate side effects
- Graceful behavior on Redis errors
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.idempotency_service import (
    DEFAULT_IDEMPOTENCY_TTL_SECONDS,
    IDEMPOTENCY_KEY_PREFIX,
    IdempotencyResult,
    IdempotencyService,
    IdempotencyStatus,
    JobDeduplicator,
    _build_idem_key,
    _compute_body_hash,
)


# =============================================================================
# Helper / Key Construction Tests
# =============================================================================


class TestKeyConstruction:
    """Tests for idempotency key building."""

    def test_build_idem_key_format(self):
        """Key includes prefix, operation, actor, and idempotency key."""
        key = _build_idem_key("user123", "create_sale", "abc-def")
        assert key == f"{IDEMPOTENCY_KEY_PREFIX}:create_sale:user123:abc-def"

    def test_compute_body_hash_bytes(self):
        """Body hash works with bytes input."""
        h = _compute_body_hash(b'{"amount": 100}')
        assert isinstance(h, str) and len(h) == 64

    def test_compute_body_hash_str(self):
        """Body hash works with string input."""
        h = _compute_body_hash('{"amount": 100}')
        assert isinstance(h, str) and len(h) == 64

    def test_compute_body_hash_dict(self):
        """Body hash works with dict input (sorted keys for determinism)."""
        h1 = _compute_body_hash({"b": 2, "a": 1})
        h2 = _compute_body_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_bodies_different_hashes(self):
        """Different bodies produce different hashes."""
        h1 = _compute_body_hash({"amount": 100})
        h2 = _compute_body_hash({"amount": 200})
        assert h1 != h2


# =============================================================================
# IdempotencyService Tests
# =============================================================================


class TestIdempotencyServiceNewRequest:
    """Tests for new (first-time) idempotency requests."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def service(self, mock_redis):
        return IdempotencyService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_new_request_returns_new_status(self, service, mock_redis):
        """First request with a given key returns NEW status."""
        result = await service.check(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
            request_body={"items": [{"id": "part1", "qty": 2}]},
        )
        assert result.status == IdempotencyStatus.NEW

    @pytest.mark.asyncio
    async def test_new_request_claims_with_nx(self, service, mock_redis):
        """First request uses SET NX to atomically claim the key."""
        await service.check(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
            request_body={"items": []},
        )
        mock_redis.set.assert_called_once()
        call_kwargs = mock_redis.set.call_args.kwargs
        assert call_kwargs.get("nx") is True
        assert call_kwargs.get("ex") == DEFAULT_IDEMPOTENCY_TTL_SECONDS


class TestIdempotencyServiceRetry:
    """Tests for valid retry (hit) scenarios."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        body = {"items": [{"id": "part1", "qty": 2}]}
        body_hash = _compute_body_hash(body)
        stored = json.dumps({
            "body_hash": body_hash,
            "state": "complete",
            "response": {"sale_id": "s-123", "total": "100.00"},
            "status_code": 201,
        })
        redis.get = AsyncMock(return_value=stored)
        redis.set = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def service(self, mock_redis):
        return IdempotencyService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_retry_returns_hit_with_stored_response(self, service):
        """A valid retry returns HIT with the original response."""
        result = await service.check(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
            request_body={"items": [{"id": "part1", "qty": 2}]},
        )
        assert result.status == IdempotencyStatus.HIT
        assert result.stored_response == {"sale_id": "s-123", "total": "100.00"}
        assert result.stored_status_code == 201


class TestIdempotencyServiceConflict:
    """Tests for body consistency violation (conflict)."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        # Stored with one body hash but we'll send a different body
        stored = json.dumps({
            "body_hash": "aaaa" * 16,  # Different from actual body
            "state": "complete",
            "response": {"sale_id": "s-123"},
            "status_code": 201,
        })
        redis.get = AsyncMock(return_value=stored)
        redis.set = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def service(self, mock_redis):
        return IdempotencyService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_different_body_returns_conflict(self, service):
        """Reusing a key with a different body returns CONFLICT."""
        result = await service.check(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
            request_body={"items": [{"id": "different", "qty": 99}]},
        )
        assert result.status == IdempotencyStatus.CONFLICT


class TestIdempotencyServiceInProgress:
    """Tests for concurrent duplicate detection (in-progress)."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        body = {"items": []}
        body_hash = _compute_body_hash(body)
        stored = json.dumps({
            "body_hash": body_hash,
            "state": "processing",
        })
        redis.get = AsyncMock(return_value=stored)
        redis.set = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def service(self, mock_redis):
        return IdempotencyService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_in_progress_returns_in_progress_status(self, service):
        """A request still processing returns IN_PROGRESS."""
        result = await service.check(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
            request_body={"items": []},
        )
        assert result.status == IdempotencyStatus.IN_PROGRESS


class TestIdempotencyServiceStoreResponse:
    """Tests for storing the operation result."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def service(self, mock_redis):
        return IdempotencyService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_store_response_persists_to_redis(self, service, mock_redis):
        """store_response writes the response body and status code."""
        await service.store_response(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
            request_body={"items": []},
            response_body={"sale_id": "s-456"},
            status_code=201,
        )
        mock_redis.set.assert_called_once()
        stored_json = mock_redis.set.call_args[0][1]
        stored = json.loads(stored_json)
        assert stored["state"] == "complete"
        assert stored["response"] == {"sale_id": "s-456"}
        assert stored["status_code"] == 201


class TestIdempotencyServiceClear:
    """Tests for clearing an idempotency key on failure."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def service(self, mock_redis):
        return IdempotencyService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_clear_deletes_redis_key(self, service, mock_redis):
        """clear() removes the idempotency marker."""
        await service.clear(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
        )
        mock_redis.delete.assert_called_once()


# =============================================================================
# IdempotencyService Error Handling
# =============================================================================


class TestIdempotencyServiceErrors:
    """Tests for graceful behavior when Redis is unavailable."""

    @pytest.fixture
    def broken_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        redis.delete = AsyncMock(side_effect=ConnectionError("Redis down"))
        return redis

    @pytest.fixture
    def service(self, broken_redis):
        return IdempotencyService(redis_client=broken_redis)

    @pytest.mark.asyncio
    async def test_check_fails_open_on_redis_error(self, service):
        """When Redis is down, check() returns NEW (fail-open)."""
        result = await service.check(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
            request_body={"items": []},
        )
        assert result.status == IdempotencyStatus.NEW

    @pytest.mark.asyncio
    async def test_store_does_not_raise_on_redis_error(self, service):
        """store_response() completes without raising on Redis error."""
        await service.store_response(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
            request_body={"items": []},
            response_body={"id": "x"},
            status_code=201,
        )

    @pytest.mark.asyncio
    async def test_clear_does_not_raise_on_redis_error(self, service):
        """clear() completes without raising on Redis error."""
        await service.clear(
            actor_id="user1",
            operation="create_sale",
            idempotency_key="key-001",
        )


# =============================================================================
# JobDeduplicator Tests
# =============================================================================


class TestJobDeduplicator:
    """Tests for background job deduplication."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.exists = AsyncMock(return_value=0)
        return redis

    @pytest.fixture
    def deduplicator(self, mock_redis):
        return JobDeduplicator(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_try_claim_succeeds_first_time(self, deduplicator, mock_redis):
        """First claim for a job key succeeds."""
        mock_redis.set.return_value = True
        result = await deduplicator.try_claim("email:user@example.com:reset-abc")
        assert result is True

    @pytest.mark.asyncio
    async def test_try_claim_fails_on_duplicate(self, deduplicator, mock_redis):
        """Second claim for the same job key fails (duplicate)."""
        mock_redis.set.return_value = False
        result = await deduplicator.try_claim("email:user@example.com:reset-abc")
        assert result is False

    @pytest.mark.asyncio
    async def test_release_removes_claim(self, deduplicator, mock_redis):
        """Release removes the deduplication key."""
        await deduplicator.release("email:user@example.com:reset-abc")
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_claimed_false_when_unclaimed(self, deduplicator, mock_redis):
        """is_claimed returns False for unclaimed keys."""
        mock_redis.exists.return_value = 0
        result = await deduplicator.is_claimed("some-job-key")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_claimed_true_when_claimed(self, deduplicator, mock_redis):
        """is_claimed returns True for claimed keys."""
        mock_redis.exists.return_value = 1
        result = await deduplicator.is_claimed("some-job-key")
        assert result is True

    @pytest.mark.asyncio
    async def test_try_claim_fails_open_on_redis_error(self, mock_redis):
        """On Redis error, try_claim returns True (fail-open)."""
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        deduplicator = JobDeduplicator(redis_client=mock_redis)
        result = await deduplicator.try_claim("job-key")
        assert result is True


# =============================================================================
# Concurrency Tests: Proving Duplicate Requests Don't Duplicate Side Effects
# =============================================================================


class TestIdempotencyConcurrency:
    """Tests proving that concurrent duplicate requests do not produce
    duplicate side effects when idempotency keys are used.

    Validates: Requirements 17.5, 17.6
    """

    @pytest.mark.asyncio
    async def test_concurrent_requests_only_one_executes(self):
        """Only one of N concurrent duplicate requests gets NEW status.

        Simulates a race condition where multiple identical requests arrive
        simultaneously. The SET NX semantics ensure only one request wins.
        """
        # Use a real dict to simulate Redis state
        store: dict[str, str] = {}

        async def mock_get(key):
            return store.get(key)

        async def mock_set(key, value, ex=None, nx=False):
            if nx and key in store:
                return False  # NX fails if key exists
            store[key] = value
            return True

        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=mock_get)
        redis.set = AsyncMock(side_effect=mock_set)

        service = IdempotencyService(redis_client=redis)

        body = {"customer_id": "c1", "items": [{"part": "p1", "qty": 1}]}
        results = []

        async def make_request():
            result = await service.check(
                actor_id="user1",
                operation="create_sale",
                idempotency_key="sale-key-001",
                request_body=body,
            )
            results.append(result.status)

        # Fire 5 concurrent requests
        await asyncio.gather(*[make_request() for _ in range(5)])

        # Exactly one should be NEW, the rest should be IN_PROGRESS
        new_count = results.count(IdempotencyStatus.NEW)
        assert new_count == 1, f"Expected 1 NEW, got {new_count}: {results}"

    @pytest.mark.asyncio
    async def test_concurrent_job_claims_only_one_wins(self):
        """Only one worker claims a deduplication slot for the same job."""
        store: dict[str, str] = {}

        async def mock_set(key, value, ex=None, nx=False):
            if nx and key in store:
                return False
            store[key] = value
            return True

        redis = AsyncMock()
        redis.set = AsyncMock(side_effect=mock_set)

        deduplicator = JobDeduplicator(redis_client=redis)

        results = []

        async def claim_job():
            result = await deduplicator.try_claim("email:user@example.com:reset-token-xyz")
            results.append(result)

        # 5 workers try to claim the same job
        await asyncio.gather(*[claim_job() for _ in range(5)])

        # Exactly one should succeed
        assert results.count(True) == 1
        assert results.count(False) == 4

    @pytest.mark.asyncio
    async def test_retry_after_completion_returns_original_response(self):
        """After the first request completes, retries return the stored response
        without executing the operation again.
        """
        body = {"customer_id": "c1", "items": [{"part": "p1", "qty": 1}]}
        body_hash = _compute_body_hash(body)

        # Simulate Redis with a completed entry
        completed_entry = json.dumps({
            "body_hash": body_hash,
            "state": "complete",
            "response": {"sale_id": "sale-001", "total": "50.00"},
            "status_code": 201,
        })

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=completed_entry)
        redis.set = AsyncMock(return_value=True)

        service = IdempotencyService(redis_client=redis)

        # Multiple retries all get the same response
        for _ in range(10):
            result = await service.check(
                actor_id="user1",
                operation="create_sale",
                idempotency_key="sale-key-002",
                request_body=body,
            )
            assert result.status == IdempotencyStatus.HIT
            assert result.stored_response == {"sale_id": "sale-001", "total": "50.00"}
            assert result.stored_status_code == 201

    @pytest.mark.asyncio
    async def test_body_mismatch_prevents_duplicate_with_different_data(self):
        """If a client reuses an idempotency key with different data, the
        service returns CONFLICT to prevent silent data corruption.
        """
        original_body = {"amount": 100}
        original_hash = _compute_body_hash(original_body)

        stored = json.dumps({
            "body_hash": original_hash,
            "state": "complete",
            "response": {"id": "tx-1"},
            "status_code": 201,
        })

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=stored)
        redis.set = AsyncMock(return_value=True)

        service = IdempotencyService(redis_client=redis)

        # Try with a different body using the same key
        result = await service.check(
            actor_id="user1",
            operation="stock_movement",
            idempotency_key="move-key-001",
            request_body={"amount": 999},  # Different!
        )
        assert result.status == IdempotencyStatus.CONFLICT
