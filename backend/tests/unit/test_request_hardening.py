"""Focused tests for CORS, request-size, and authentication rate hardening."""

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.config import Settings
from app.middleware.request_size import RequestSizeMiddleware
from app.routers.auth import router as auth_router


class TestCorsPolicy:
    def test_preflight_allows_only_required_methods_and_headers(self):
        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["https://frontend.example"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

        @app.post("/resource")
        async def resource():
            return {"ok": True}

        response = TestClient(app).options(
            "/resource",
            headers={
                "Origin": "https://frontend.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-methods"] == (
            "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        )
        allowed_headers = response.headers["access-control-allow-headers"]
        assert "Authorization" in allowed_headers
        assert "Content-Type" in allowed_headers
        assert "*" not in allowed_headers


class TestRequestSizeMiddleware:
    def test_rejects_content_length_before_route_execution(self):
        app = FastAPI()
        app.add_middleware(RequestSizeMiddleware, max_body_size=4)
        called = False

        @app.post("/upload")
        async def upload():
            nonlocal called
            called = True
            return {"ok": True}

        response = TestClient(app).post("/upload", content=b"12345")

        assert response.status_code == 413
        assert response.json() == {"detail": "Request body too large"}
        assert called is False

    @pytest.mark.asyncio
    async def test_rejects_chunked_body_after_streamed_limit_is_exceeded(self):
        app = FastAPI()
        app.add_middleware(RequestSizeMiddleware, max_body_size=4)

        @app.post("/upload")
        async def upload(request: Request):
            await request.body()
            return {"ok": True}

        messages = [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ]
        response_messages: list[dict] = []

        async def receive():
            return messages.pop(0)

        async def send(message):
            response_messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/upload",
                "raw_path": b"/upload",
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 50000),
                "server": ("testserver", 80),
            },
            receive,
            send,
        )

        assert response_messages[0]["status"] == 413
        assert json.loads(response_messages[1]["body"]) == {
            "detail": "Request body too large"
        }


class TestAuthenticationRateLimits:
    def test_auth_routes_have_strict_configured_limits(self):
        settings = Settings(
            jwt_secret_key="test-secret-key-for-rate-limit-tests",
            database_url="postgresql+asyncpg://test:test@localhost/test_db",
            rate_limit_login=5,
            rate_limit_refresh=10,
            rate_limit_password_reset=5,
            rate_limit_password_reset_confirm=5,
        )
        expected = {
            "/api/v1/auth/login": "5/minute",
            "/api/v1/auth/refresh": "10/minute",
            "/api/v1/auth/reset-password": "5/minute",
            "/api/v1/auth/reset-password/confirm": "5/minute",
        }

        from app.middleware.rate_limit import get_rate_limiter
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [],
            "client": ("127.0.0.1", 1),
        }
        request = Request(scope)
        limiter = get_rate_limiter()

        with patch("app.middleware.rate_limit.get_settings", return_value=settings):
            for route in auth_router.routes:
                if route.path not in expected:
                    continue
                route_name = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
                limit_group = limiter._dynamic_route_limits[route_name][0]
                limit_callable = limit_group._LimitGroup__limit_provider
                assert limit_callable(request) == expected[route.path]

        assert settings.rate_limit_login < settings.rate_limit_unauthenticated
        assert settings.rate_limit_refresh < settings.rate_limit_unauthenticated
        assert settings.rate_limit_password_reset < settings.rate_limit_unauthenticated
        assert (
            settings.rate_limit_password_reset_confirm
            < settings.rate_limit_unauthenticated
        )
