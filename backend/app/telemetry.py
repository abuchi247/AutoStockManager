"""Provider-neutral metrics, tracing, and telemetry adapter.

This module exposes an abstract ``TelemetryAdapter`` interface and a concrete
``InMemoryTelemetry`` implementation suitable for local development and testing.
Production deployments can swap in a provider-specific adapter (e.g. Prometheus,
Datadog, OpenTelemetry) behind the same interface without changing application
code.

Telemetry covers:
- Request count, status class, and latency histograms
- Database pool wait time and slow-query counts
- Redis command failures and latency
- Background queue depth and job duration/failures
- Worker concurrency and dependency health

Trace/request IDs are propagated through logs, error tracking, and background
jobs.  Sensitive fields are redacted before export.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.middleware.request_id import request_id_var

logger = logging.getLogger(__name__)

# Trace ID context variable; separate from request_id to allow distributed
# tracing across service boundaries.  Falls back to request_id when not set
# explicitly by an upstream header.
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

# Fields that must never appear in exported telemetry attributes
_REDACTED_FIELDS = frozenset(
    {
        "authorization",
        "cookie",
        "password",
        "passwd",
        "secret",
        "token",
        "credential",
        "api_key",
        "apikey",
        "database_url",
        "dsn",
        "refresh_token",
        "reset_token",
        "jwt",
    }
)

REDACTED = "[REDACTED]"


def _is_sensitive(name: str) -> bool:
    """Check if an attribute name contains sensitive content."""
    normalized = name.lower().replace("-", "_")
    return any(part in normalized for part in _REDACTED_FIELDS)


def redact_attributes(attrs: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of attributes with sensitive values replaced."""
    return {
        key: REDACTED if _is_sensitive(key) else value
        for key, value in attrs.items()
    }


def get_trace_context() -> dict[str, str | None]:
    """Return the current trace and request IDs for log/job propagation."""
    return {
        "request_id": request_id_var.get(),
        "trace_id": trace_id_var.get() or request_id_var.get(),
    }


@dataclass
class LatencyRecord:
    """Lightweight latency observation."""

    name: str
    duration_ms: float
    attributes: dict[str, Any] = field(default_factory=dict)


class TelemetryAdapter(Protocol):
    """Provider-neutral telemetry interface.

    Implementations may export to Prometheus, OpenTelemetry, Datadog, or any
    compatible backend.  The InMemoryTelemetry implementation stores counters
    in process memory for testing and development.
    """

    def increment_counter(
        self, name: str, value: int = 1, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        """Increment a named counter metric."""
        ...

    def record_histogram(
        self, name: str, value: float, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        """Record a value in a named histogram (e.g. latency)."""
        ...

    def set_gauge(
        self, name: str, value: float, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        """Set a gauge to the given value."""
        ...

    def record_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record an HTTP request with standard dimensions."""
        ...

    def record_db_pool_wait(self, duration_ms: float) -> None:
        """Record database connection pool acquisition time."""
        ...

    def record_db_slow_query(self, duration_ms: float, *, statement: str = "") -> None:
        """Record a slow database query event."""
        ...

    def record_redis_error(self, *, operation: str = "unknown") -> None:
        """Record a Redis command failure."""
        ...

    def record_redis_latency(self, duration_ms: float) -> None:
        """Record Redis command latency."""
        ...

    def record_queue_depth(self, depth: int) -> None:
        """Record current background queue depth."""
        ...

    def record_job_duration(
        self, *, job_name: str, duration_ms: float, success: bool
    ) -> None:
        """Record a background job execution."""
        ...

    def record_worker_concurrency(self, active_count: int) -> None:
        """Record the number of concurrently executing workers."""
        ...

    def record_dependency_health(
        self, *, dependency: str, healthy: bool
    ) -> None:
        """Record the health status of an external dependency."""
        ...


class NoOpTelemetry:
    """Telemetry adapter that does nothing.  Used when telemetry is disabled."""

    def increment_counter(
        self, name: str, value: int = 1, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        pass

    def record_histogram(
        self, name: str, value: float, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        pass

    def set_gauge(
        self, name: str, value: float, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        pass

    def record_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        pass

    def record_db_pool_wait(self, duration_ms: float) -> None:
        pass

    def record_db_slow_query(self, duration_ms: float, *, statement: str = "") -> None:
        pass

    def record_redis_error(self, *, operation: str = "unknown") -> None:
        pass

    def record_redis_latency(self, duration_ms: float) -> None:
        pass

    def record_queue_depth(self, depth: int) -> None:
        pass

    def record_job_duration(
        self, *, job_name: str, duration_ms: float, success: bool
    ) -> None:
        pass

    def record_worker_concurrency(self, active_count: int) -> None:
        pass

    def record_dependency_health(
        self, *, dependency: str, healthy: bool
    ) -> None:
        pass


class InMemoryTelemetry:
    """In-process telemetry adapter for testing and development.

    Stores all metrics in memory for inspection.  Not suitable for production
    multi-process deployments but useful for verifying instrumentation.
    """

    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.gauges: dict[str, float] = {}
        self.requests: list[dict[str, Any]] = []
        self.db_pool_waits: list[float] = []
        self.db_slow_queries: list[dict[str, Any]] = []
        self.redis_errors: list[dict[str, Any]] = []
        self.redis_latencies: list[float] = []
        self.queue_depths: list[int] = []
        self.job_durations: list[dict[str, Any]] = []
        self.worker_concurrency: list[int] = []
        self.dependency_health: dict[str, bool] = {}

    def increment_counter(
        self, name: str, value: int = 1, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        safe_attrs = redact_attributes(attributes or {})
        key = f"{name}:{safe_attrs}" if safe_attrs else name
        self.counters[key] += value

    def record_histogram(
        self, name: str, value: float, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        safe_attrs = redact_attributes(attributes or {})
        key = f"{name}:{safe_attrs}" if safe_attrs else name
        self.histograms[key].append(value)

    def set_gauge(
        self, name: str, value: float, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        safe_attrs = redact_attributes(attributes or {})
        key = f"{name}:{safe_attrs}" if safe_attrs else name
        self.gauges[key] = value

    def record_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        self.requests.append(
            {
                "method": method,
                "route": route,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "status_class": f"{status_code // 100}xx",
            }
        )
        self.increment_counter(
            "http_requests_total",
            attributes={"method": method, "route": route, "status_class": f"{status_code // 100}xx"},
        )
        self.record_histogram(
            "http_request_duration_ms",
            duration_ms,
            attributes={"method": method, "route": route},
        )

    def record_db_pool_wait(self, duration_ms: float) -> None:
        self.db_pool_waits.append(duration_ms)
        self.record_histogram("db_pool_wait_ms", duration_ms)

    def record_db_slow_query(self, duration_ms: float, *, statement: str = "") -> None:
        self.db_slow_queries.append(
            {"duration_ms": duration_ms, "statement": statement[:200]}
        )
        self.increment_counter("db_slow_queries_total")

    def record_redis_error(self, *, operation: str = "unknown") -> None:
        self.redis_errors.append({"operation": operation})
        self.increment_counter("redis_errors_total", attributes={"operation": operation})

    def record_redis_latency(self, duration_ms: float) -> None:
        self.redis_latencies.append(duration_ms)
        self.record_histogram("redis_latency_ms", duration_ms)

    def record_queue_depth(self, depth: int) -> None:
        self.queue_depths.append(depth)
        self.set_gauge("queue_depth", float(depth))

    def record_job_duration(
        self, *, job_name: str, duration_ms: float, success: bool
    ) -> None:
        self.job_durations.append(
            {"job_name": job_name, "duration_ms": duration_ms, "success": success}
        )
        status = "success" if success else "failure"
        self.record_histogram(
            "job_duration_ms",
            duration_ms,
            attributes={"job_name": job_name, "status": status},
        )
        if not success:
            self.increment_counter(
                "job_failures_total", attributes={"job_name": job_name}
            )

    def record_worker_concurrency(self, active_count: int) -> None:
        self.worker_concurrency.append(active_count)
        self.set_gauge("worker_active_count", float(active_count))

    def record_dependency_health(
        self, *, dependency: str, healthy: bool
    ) -> None:
        self.dependency_health[dependency] = healthy
        self.set_gauge(
            "dependency_healthy",
            1.0 if healthy else 0.0,
            attributes={"dependency": dependency},
        )

    def reset(self) -> None:
        """Clear all stored telemetry (useful between test cases)."""
        self.counters.clear()
        self.histograms.clear()
        self.gauges.clear()
        self.requests.clear()
        self.db_pool_waits.clear()
        self.db_slow_queries.clear()
        self.redis_errors.clear()
        self.redis_latencies.clear()
        self.queue_depths.clear()
        self.job_durations.clear()
        self.worker_concurrency.clear()
        self.dependency_health.clear()


class LoggingTelemetry:
    """Telemetry adapter that emits metrics as structured log records.

    Suitable for production environments that ingest structured logs into a
    metrics pipeline (e.g. CloudWatch, Datadog Log Metrics, Loki).
    """

    def __init__(self, *, slow_query_threshold_ms: float = 200.0) -> None:
        self._slow_query_threshold_ms = slow_query_threshold_ms

    def increment_counter(
        self, name: str, value: int = 1, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        safe_attrs = redact_attributes(attributes or {})
        logger.info(
            "metric_counter",
            extra={"metric_name": name, "metric_value": value, **safe_attrs},
        )

    def record_histogram(
        self, name: str, value: float, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        safe_attrs = redact_attributes(attributes or {})
        logger.info(
            "metric_histogram",
            extra={"metric_name": name, "metric_value": value, **safe_attrs},
        )

    def set_gauge(
        self, name: str, value: float, *, attributes: Mapping[str, Any] | None = None
    ) -> None:
        safe_attrs = redact_attributes(attributes or {})
        logger.info(
            "metric_gauge",
            extra={"metric_name": name, "metric_value": value, **safe_attrs},
        )

    def record_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        logger.info(
            "http_request",
            extra={
                "method": method,
                "route": route,
                "status_code": status_code,
                "status_class": f"{status_code // 100}xx",
                "duration_ms": round(duration_ms, 2),
                **get_trace_context(),
            },
        )

    def record_db_pool_wait(self, duration_ms: float) -> None:
        logger.info(
            "db_pool_wait",
            extra={"duration_ms": round(duration_ms, 2), **get_trace_context()},
        )

    def record_db_slow_query(self, duration_ms: float, *, statement: str = "") -> None:
        # Truncate statement to avoid logging massive SQL
        safe_statement = statement[:200] if statement else ""
        logger.warning(
            "db_slow_query",
            extra={
                "duration_ms": round(duration_ms, 2),
                "statement_prefix": safe_statement,
                **get_trace_context(),
            },
        )

    def record_redis_error(self, *, operation: str = "unknown") -> None:
        logger.warning(
            "redis_error",
            extra={"operation": operation, **get_trace_context()},
        )

    def record_redis_latency(self, duration_ms: float) -> None:
        logger.info(
            "redis_latency",
            extra={"duration_ms": round(duration_ms, 2), **get_trace_context()},
        )

    def record_queue_depth(self, depth: int) -> None:
        logger.info(
            "queue_depth",
            extra={"depth": depth, **get_trace_context()},
        )

    def record_job_duration(
        self, *, job_name: str, duration_ms: float, success: bool
    ) -> None:
        level = logging.INFO if success else logging.WARNING
        logger.log(
            level,
            "job_completed",
            extra={
                "job_name": job_name,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                **get_trace_context(),
            },
        )

    def record_worker_concurrency(self, active_count: int) -> None:
        logger.info(
            "worker_concurrency",
            extra={"active_count": active_count, **get_trace_context()},
        )

    def record_dependency_health(
        self, *, dependency: str, healthy: bool
    ) -> None:
        level = logging.INFO if healthy else logging.WARNING
        logger.log(
            level,
            "dependency_health",
            extra={"dependency": dependency, "healthy": healthy, **get_trace_context()},
        )


# Module-level telemetry instance; replaced by create_telemetry during startup.
_telemetry: TelemetryAdapter = NoOpTelemetry()


def get_telemetry() -> TelemetryAdapter:
    """Return the active telemetry adapter."""
    return _telemetry


def set_telemetry(adapter: TelemetryAdapter) -> None:
    """Replace the module-level telemetry adapter (e.g. during startup)."""
    global _telemetry
    _telemetry = adapter


def create_telemetry(*, environment: str, enabled: bool = True) -> TelemetryAdapter:
    """Build and activate the appropriate telemetry adapter.

    - ``NoOpTelemetry`` when disabled.
    - ``InMemoryTelemetry`` in development/testing.
    - ``LoggingTelemetry`` in staging/production when structured logging is
      sufficient for the metrics pipeline.

    Provider-specific exporters (Prometheus, OpenTelemetry) can be added as
    additional concrete adapters without changing calling code.
    """
    if not enabled:
        adapter: TelemetryAdapter = NoOpTelemetry()
    elif environment in ("staging", "production"):
        adapter = LoggingTelemetry()
    else:
        adapter = InMemoryTelemetry()

    set_telemetry(adapter)
    return adapter
