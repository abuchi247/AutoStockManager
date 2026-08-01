"""Performance budgets and SLO threshold definitions.

This module codifies the performance budgets documented in the operations runbook
as programmatic thresholds that can be validated in CI, staging performance checks,
and production alerting pipelines.

Budgets are starting points derived from expected workloads.  They must be
recalibrated from production evidence within the first release cycle and reviewed
quarterly.  See OPERATIONS_RUNBOOK.md Section 10 for the full recalibration process.

Requirements: 17.7, 17.8, 19.1, 19.7
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LatencyBudget:
    """Latency threshold for a route category."""

    category: str
    p95_ms: float
    description: str = ""


@dataclass(frozen=True)
class ErrorRateBudget:
    """Error rate threshold as a percentage of total requests."""

    category: str
    max_percent: float
    description: str = ""


@dataclass(frozen=True)
class ResourceBudget:
    """Resource utilisation threshold (pool saturation, queue depth, etc.)."""

    metric: str
    warning_threshold: float
    critical_threshold: float
    unit: str = ""
    description: str = ""


@dataclass(frozen=True)
class PerformanceBudgets:
    """Collection of all defined performance budgets.

    These thresholds are used by:
    - CI test assertions to detect regressions
    - Staging performance checks against production-like data
    - Production alerting pipelines consuming structured telemetry logs
    """

    latency_budgets: tuple[LatencyBudget, ...] = field(default_factory=tuple)
    error_rate_budgets: tuple[ErrorRateBudget, ...] = field(default_factory=tuple)
    resource_budgets: tuple[ResourceBudget, ...] = field(default_factory=tuple)

    def get_latency_budget(self, category: str) -> LatencyBudget | None:
        """Return the latency budget for a given category, or None."""
        for budget in self.latency_budgets:
            if budget.category == category:
                return budget
        return None

    def get_error_rate_budget(self, category: str) -> ErrorRateBudget | None:
        """Return the error rate budget for a given category, or None."""
        for budget in self.error_rate_budgets:
            if budget.category == category:
                return budget
        return None

    def check_latency(self, category: str, observed_p95_ms: float) -> bool:
        """Return True if the observed p95 latency is within budget."""
        budget = self.get_latency_budget(category)
        if budget is None:
            return True  # No budget defined means no constraint
        return observed_p95_ms <= budget.p95_ms

    def check_error_rate(self, category: str, observed_percent: float) -> bool:
        """Return True if the observed error rate is within budget."""
        budget = self.get_error_rate_budget(category)
        if budget is None:
            return True
        return observed_percent <= budget.max_percent

    def check_resource(self, metric: str, observed_value: float) -> str:
        """Return 'ok', 'warning', or 'critical' based on the observed value."""
        for budget in self.resource_budgets:
            if budget.metric == metric:
                if observed_value >= budget.critical_threshold:
                    return "critical"
                if observed_value >= budget.warning_threshold:
                    return "warning"
                return "ok"
        return "ok"

    def summary(self) -> dict[str, Any]:
        """Return a JSON-serializable summary of all budgets."""
        return {
            "latency": [
                {"category": b.category, "p95_ms": b.p95_ms}
                for b in self.latency_budgets
            ],
            "error_rates": [
                {"category": b.category, "max_percent": b.max_percent}
                for b in self.error_rate_budgets
            ],
            "resources": [
                {
                    "metric": b.metric,
                    "warning": b.warning_threshold,
                    "critical": b.critical_threshold,
                    "unit": b.unit,
                }
                for b in self.resource_budgets
            ],
        }


# ---------------------------------------------------------------------------
# Default production budgets (aligned with OPERATIONS_RUNBOOK.md Section 10)
# ---------------------------------------------------------------------------

API_PERFORMANCE_BUDGETS = PerformanceBudgets(
    latency_budgets=(
        LatencyBudget(
            category="crud",
            p95_ms=500.0,
            description="Authenticated CRUD endpoints",
        ),
        LatencyBudget(
            category="reports",
            p95_ms=2000.0,
            description="Report and export endpoints",
        ),
        LatencyBudget(
            category="auth",
            p95_ms=300.0,
            description="Login, refresh, and logout",
        ),
        LatencyBudget(
            category="health",
            p95_ms=500.0,
            description="Health check endpoint (p99)",
        ),
    ),
    error_rate_budgets=(
        ErrorRateBudget(
            category="api",
            max_percent=1.0,
            description="5xx error rate excluding expected 4xx",
        ),
    ),
    resource_budgets=(
        ResourceBudget(
            metric="db_pool_saturation_percent",
            warning_threshold=80.0,
            critical_threshold=95.0,
            unit="percent",
            description="Database connection pool utilisation",
        ),
        ResourceBudget(
            metric="db_pool_wait_p95_ms",
            warning_threshold=100.0,
            critical_threshold=500.0,
            unit="ms",
            description="Database pool acquisition time (p95)",
        ),
        ResourceBudget(
            metric="queue_depth",
            warning_threshold=100.0,
            critical_threshold=500.0,
            unit="jobs",
            description="Sustained pending background job count",
        ),
        ResourceBudget(
            metric="redis_errors_per_min",
            warning_threshold=5.0,
            critical_threshold=10.0,
            unit="errors/min",
            description="Redis command failure rate",
        ),
        ResourceBudget(
            metric="job_failure_rate_percent",
            warning_threshold=2.0,
            critical_threshold=5.0,
            unit="percent",
            description="Worker job terminal failure rate",
        ),
    ),
)


def get_performance_budgets() -> PerformanceBudgets:
    """Return the active performance budgets for CI and production checks."""
    return API_PERFORMANCE_BUDGETS
