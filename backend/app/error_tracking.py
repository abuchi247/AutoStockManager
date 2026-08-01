"""Safe, provider-neutral error tracking adapters.

The application reports only deliberately constructed request context to this
module.  Provider setup is lazy/optional so local development does not require
an error-tracking SDK or network access.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Protocol

from app.config import Settings

logger = logging.getLogger(__name__)

REDACTED = "[REDACTED]"
_SENSITIVE_NAME_PARTS = (
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
)


class ErrorTracker(Protocol):
    """Minimal interface used by the global exception handler."""

    def capture_exception(
        self, exception: BaseException, *, context: Mapping[str, Any]
    ) -> None:
        """Report an exception with already-scrubbed context."""


class NoOpErrorTracker:
    """Tracker used by default and whenever reporting is disabled."""

    def capture_exception(
        self, exception: BaseException, *, context: Mapping[str, Any]
    ) -> None:
        del exception, context


def _is_sensitive_name(name: object) -> bool:
    normalized = str(name).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_NAME_PARTS)


def scrub_value(value: Any) -> Any:
    """Recursively remove common credentials from provider-bound values."""
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_sensitive_name(key) else scrub_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [scrub_value(item) for item in value]
    return value


def scrub_headers(headers: Mapping[str, Any]) -> dict[str, Any]:
    """Return headers safe to attach to an error event."""
    return {
        str(key): REDACTED if _is_sensitive_name(key) else str(value)
        for key, value in headers.items()
    }


class SentryErrorTracker:
    """Sentry-compatible adapter with no direct dependency on the SDK.

    Deployments that enable this adapter provide ``sentry-sdk``.  The optional
    ``sdk`` argument makes the adapter straightforward to test and also keeps
    the application importable when tracking is disabled locally.
    """

    def __init__(
        self,
        *,
        dsn: str,
        environment: str,
        release: str | None = None,
        sample_rate: float = 1.0,
        sdk: Any | None = None,
    ) -> None:
        if sdk is None:
            try:
                import sentry_sdk as sdk_module
            except ImportError as error:  # pragma: no cover - deployment-only path
                raise RuntimeError(
                    "sentry-sdk is required when error tracking is enabled"
                ) from error
            sdk = sdk_module

        self._sdk = sdk
        sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            sample_rate=sample_rate,
        )

    def capture_exception(
        self, exception: BaseException, *, context: Mapping[str, Any]
    ) -> None:
        safe_context = scrub_value(context)
        sdk = self._sdk
        push_scope = getattr(sdk, "push_scope", None)
        if push_scope is None:  # Useful for small provider-compatible clients.
            sdk.capture_exception(exception)
            return

        with push_scope() as scope:
            request_context = safe_context.get("request", safe_context)
            set_context = getattr(scope, "set_context", None)
            if set_context is not None:
                set_context("request", request_context)

            user_id = safe_context.get("user_id")
            if user_id:
                set_user = getattr(scope, "set_user", None)
                if set_user is not None:
                    set_user({"id": str(user_id)})

            sdk.capture_exception(exception)


def create_error_tracker(settings: Settings) -> ErrorTracker:
    """Build the configured tracker, failing safe if optional reporting is unavailable."""
    if not settings.error_tracker_enabled or not settings.error_tracker_dsn:
        return NoOpErrorTracker()

    try:
        return SentryErrorTracker(
            dsn=settings.error_tracker_dsn,
            environment=settings.error_tracker_environment or settings.environment,
            release=settings.error_tracker_release or settings.app_version,
            sample_rate=settings.error_tracker_sample_rate,
        )
    except Exception:
        # Error reporting must never prevent a request from receiving a safe
        # response or prevent local development from starting.
        logger.warning("Error tracker unavailable; continuing without reporting")
        return NoOpErrorTracker()
