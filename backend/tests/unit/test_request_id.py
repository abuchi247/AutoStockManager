"""Tests for request ID propagation and request-scoped logging context."""

import asyncio
import uuid

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware.request_id import (
    REQUEST_ID_HEADER,
    RequestIDMiddleware,
    get_request_id,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/context")
    async def context_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "state": request.state.request_id,
                "context": get_request_id(),
            }
        )

    @app.get("/error")
    async def error_endpoint() -> None:
        raise HTTPException(status_code=422, detail="expected error")

    @app.get("/slow/{request_name}")
    async def slow_endpoint(request_name: str, request: Request) -> JSONResponse:
        await asyncio.sleep(0.01)
        return JSONResponse(
            {
                "name": request_name,
                "state": request.state.request_id,
                "context": get_request_id(),
            }
        )

    return app


class TestRequestIDMiddleware:
    def test_propagates_valid_incoming_request_id_to_state_context_and_response(self):
        app = _make_app()
        client = TestClient(app)

        response = client.get("/context", headers={REQUEST_ID_HEADER: "client-request-123"})

        assert response.status_code == 200
        assert response.headers[REQUEST_ID_HEADER] == "client-request-123"
        assert response.json() == {
            "state": "client-request-123",
            "context": "client-request-123",
        }
        assert get_request_id() is None

    def test_generates_uuid_when_request_id_is_missing_or_invalid(self):
        app = _make_app()
        client = TestClient(app)

        missing_response = client.get("/context")
        invalid_response = client.get("/context", headers={REQUEST_ID_HEADER: "bad value"})

        for response in (missing_response, invalid_response):
            generated_id = response.headers[REQUEST_ID_HEADER]
            assert uuid.UUID(generated_id).version == 4
            assert response.json()["state"] == generated_id
            assert response.json()["context"] == generated_id

    def test_propagates_request_id_on_handled_error_response(self):
        app = _make_app()
        client = TestClient(app)

        response = client.get("/error", headers={REQUEST_ID_HEADER: "error-request-1"})

        assert response.status_code == 422
        assert response.headers[REQUEST_ID_HEADER] == "error-request-1"

    @pytest.mark.asyncio
    async def test_request_context_is_isolated_between_concurrent_requests(self):
        app = _make_app()
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            responses = await asyncio.gather(
                client.get("/slow/first", headers={REQUEST_ID_HEADER: "request-first"}),
                client.get("/slow/second", headers={REQUEST_ID_HEADER: "request-second"}),
            )

        assert [response.status_code for response in responses] == [200, 200]
        assert responses[0].json() == {
            "name": "first",
            "state": "request-first",
            "context": "request-first",
        }
        assert responses[1].json() == {
            "name": "second",
            "state": "request-second",
            "context": "request-second",
        }
        assert get_request_id() is None
