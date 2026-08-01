"""Request correlation middleware and logging context.

A request ID is accepted from ``X-Request-ID`` only when it is a bounded,
header-safe identifier. Invalid or missing values are replaced with a UUID so
that clients cannot inject line breaks or unbounded data into response headers
or logs.
"""

from contextvars import ContextVar
import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request


REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")

# The value is available to log records emitted while a request is handled.
# Resetting the token in middleware prevents values leaking between requests.
request_id_context: ContextVar[str | None] = ContextVar(
    "request_id", default=None
)

# Alias with a concise name for logging integrations.
request_id_var = request_id_context


def get_request_id() -> str | None:
    """Return the request ID for the current asynchronous execution context."""

    return request_id_context.get()


def _is_valid_request_id(value: str | None) -> bool:
    """Return whether a client-provided request ID is safe to propagate."""

    return value is not None and _REQUEST_ID_PATTERN.fullmatch(value) is not None


class RequestIDMiddleware:
    """Propagate a request ID through state, logs, and response headers.

    This is an ASGI middleware rather than ``BaseHTTPMiddleware`` so response
    headers are added to every response start emitted by downstream FastAPI
    exception handlers as well as normal route responses.
    """

    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        incoming_request_id = request.headers.get(REQUEST_ID_HEADER)
        request_id = (
            incoming_request_id
            if _is_valid_request_id(incoming_request_id)
            else str(uuid4())
        )
        request.state.request_id = request_id
        context_token = request_id_context.set(request_id)

        async def send_with_request_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_context.reset(context_token)
