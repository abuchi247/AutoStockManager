"""ASGI middleware enforcing a maximum incoming request body size.

The middleware rejects requests with an oversized ``Content-Length`` before
application code runs and also counts received chunks for streaming/chunked
requests that do not provide a length upfront.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.types import Receive, Scope, Send


REQUEST_TOO_LARGE_DETAIL = "Request body too large"


class RequestBodyTooLarge(Exception):
    """Raised internally when a streamed request exceeds the configured limit."""


class RequestSizeMiddleware:
    """Reject request bodies larger than ``max_body_size`` bytes."""

    def __init__(self, app: Callable[..., Awaitable[Any]], max_body_size: int) -> None:
        if max_body_size <= 0:
            raise ValueError("max_body_size must be greater than zero")
        self.app = app
        self.max_body_size = max_body_size

    @staticmethod
    async def _send_rejection(send: Send) -> None:
        body = b'{"detail":"Request body too large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = scope.get("headers", [])
        declared_length: int | None = None
        for name, value in content_length:
            if name.lower() == b"content-length":
                try:
                    declared_length = int(value)
                except (TypeError, ValueError):
                    declared_length = None
                break

        if declared_length is not None and declared_length > self.max_body_size:
            await self._send_rejection(send)
            return

        received_bytes = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_size:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await self._send_rejection(send)
