"""Global FastAPI exception handling with safe error-tracker context."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.error_tracking import ErrorTracker, NoOpErrorTracker, scrub_headers, scrub_value
from app.middleware.request_id import REQUEST_ID_HEADER

logger = logging.getLogger(__name__)

_GENERIC_ERROR_DETAIL = "Internal server error"


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return str(route_path or request.url.path)


def _authenticated_user_id(request: Request) -> str | None:
    """Read only an identifier previously placed in request state by auth."""
    for attribute in ("authenticated_user_id", "user_id"):
        value = getattr(request.state, attribute, None)
        if value is not None:
            return str(value)

    user = getattr(request.state, "user", None)
    user_id = getattr(user, "id", None)
    return str(user_id) if user_id is not None else None


def build_exception_context(request: Request) -> dict[str, Any]:
    """Build a deliberately small context object safe for external reporting.

    Request bodies are intentionally never read: a body can contain credentials
    even when its field names are unknown.  Headers and any nested values are
    scrubbed as defense in depth.
    """
    user_id = _authenticated_user_id(request)
    request_context: dict[str, Any] = {
        "route": _route_template(request),
        "method": request.method,
        "request_id": getattr(request.state, "request_id", None),
        "user_id": user_id,
        "headers": scrub_headers(request.headers),
        "body": "[REDACTED]",
    }
    return {
        "request": scrub_value(request_context),
        "user_id": user_id,
    }


def _tracker_for(request: Request) -> ErrorTracker:
    tracker = getattr(request.app.state, "error_tracker", None)
    return tracker if tracker is not None else NoOpErrorTracker()


def _report(request: Request, exception: BaseException) -> None:
    context = build_exception_context(request)
    try:
        _tracker_for(request).capture_exception(exception, context=context)
    except Exception:
        # A provider outage or adapter defect must not replace the safe API
        # response, and this log contains no exception message or credentials.
        logger.warning("Error tracker failed while reporting an exception")


def _log_unhandled(request: Request, exception: Exception) -> None:
    # Do not include exception text or a traceback: either may contain secrets
    # supplied by a downstream library.  Structured logging can add the safe
    # context separately without exposing the original request payload.
    logger.error(
        "Unhandled request exception",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "route": _route_template(request),
            "method": request.method,
            "exception_type": type(exception).__name__,
        },
    )


async def unhandled_exception_handler(request: Request, exception: Exception) -> JSONResponse:
    """Report unexpected failures and return a detail-free 500 response."""
    _log_unhandled(request, exception)
    _report(request, exception)
    request_id = getattr(request.state, "request_id", None)
    headers = {REQUEST_ID_HEADER: str(request_id)} if request_id else None
    return JSONResponse(
        status_code=500,
        content={"detail": _GENERIC_ERROR_DETAIL},
        headers=headers,
    )


def install_exception_handlers(
    app: FastAPI, *, tracker: ErrorTracker | None = None
) -> None:
    """Install handlers while retaining FastAPI's safe expected-error formats."""
    app.state.error_tracker = tracker or NoOpErrorTracker()
    # FastAPI's built-in HTTP and validation handlers remain active, preserving
    # their expected status codes and safe response details.
    app.add_exception_handler(Exception, unhandled_exception_handler)
