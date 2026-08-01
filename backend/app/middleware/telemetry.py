"""Request telemetry middleware.

Records request count, latency, and status class for every HTTP request.
Propagates trace IDs from upstream headers (``X-Trace-ID``) and includes
them in response headers for distributed tracing correlation.

This middleware sits inside the request-ID middleware so both request_id
and trace_id are available in the logging/telemetry context.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.routing import Match

from app.middleware.request_id import request_id_var

TRACE_ID_HEADER = "X-Trace-ID"


def _resolve_route(scope: dict[str, Any]) -> str:
    """Resolve the matched route pattern for low-cardinality metric labels."""
    app = scope.get("app")
    if app is None:
        return scope.get("path", "unknown")
    # Walk the router to find the matched route pattern
    routes = getattr(app, "routes", [])
    for route in routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return getattr(route, "path", scope.get("path", "unknown"))
    return scope.get("path", "unknown")


class TelemetryMiddleware:
    """ASGI middleware that records request metrics and propagates trace IDs.

    Must be added inside RequestIDMiddleware so request_id_var is set.
    """

    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        # Imported lazily because ``app.telemetry`` reads the request-ID
        # context variable from this package. A module-level import here makes
        # ``app.telemetry`` -> ``app.middleware`` -> ``app.middleware.telemetry``
        # a circular import whenever telemetry is imported before the app
        # factory (for example by the ARQ worker or a single test module).
        from app.telemetry import get_telemetry, trace_id_var

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)

        # Accept or derive trace ID
        incoming_trace_id = request.headers.get(TRACE_ID_HEADER)
        trace_id = incoming_trace_id if incoming_trace_id else request_id_var.get()
        token = trace_id_var.set(trace_id)

        start_time = time.perf_counter()
        status_code = 500  # Default if response never starts

        async def send_with_telemetry(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
                # Inject trace ID into response headers
                headers = MutableHeaders(scope=message)
                if trace_id:
                    headers[TRACE_ID_HEADER] = trace_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_telemetry)
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            method = scope.get("method", "UNKNOWN")
            route = _resolve_route(scope)

            telemetry = get_telemetry()
            telemetry.record_request(
                method=method,
                route=route,
                status_code=status_code,
                duration_ms=duration_ms,
            )
            trace_id_var.reset(token)
