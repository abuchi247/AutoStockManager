"""Unit and integration coverage for safe exception reporting."""

from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.error_tracking import (
    NoOpErrorTracker,
    SentryErrorTracker,
    create_error_tracker,
)
from app.exception_handlers import install_exception_handlers
from app.middleware.request_id import RequestIDMiddleware
from app.config import Settings


class RecordingTracker:
    def __init__(self) -> None:
        self.events: list[tuple[BaseException, dict[str, Any]]] = []

    def capture_exception(self, exception: BaseException, *, context: dict[str, Any]) -> None:
        self.events.append((exception, context))


def _make_app(tracker: RecordingTracker) -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app, tracker=tracker)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("password=super-secret")

    @app.get("/expected")
    async def expected() -> None:
        raise HTTPException(status_code=409, detail="expected conflict")

    @app.get("/authenticated-boom")
    async def authenticated_boom(request: Request) -> None:
        request.state.authenticated_user_id = "user-123"
        raise RuntimeError("database failure")

    class Payload(BaseModel):
        name: str

    @app.post("/payload")
    async def payload(body: Payload) -> dict[str, str]:
        return body.model_dump()

    return app


def test_local_tracker_is_noop_by_default() -> None:
    settings = Settings(environment="development", error_tracker_enabled=False)

    assert isinstance(create_error_tracker(settings), NoOpErrorTracker)


def test_unexpected_exception_reports_only_safe_request_context() -> None:
    tracker = RecordingTracker()
    client = TestClient(_make_app(tracker), raise_server_exceptions=False)

    response = client.get(
        "/boom",
        headers={
            "X-Request-ID": "safe-request-1",
            "Authorization": "Bearer authorization-secret",
            "Cookie": "session= cookie-secret",
            "X-Trace-Note": "safe metadata",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["X-Request-ID"] == "safe-request-1"
    assert len(tracker.events) == 1

    exception, context = tracker.events[0]
    assert isinstance(exception, RuntimeError)
    request_context = context["request"]
    assert request_context["route"] == "/boom"
    assert request_context["method"] == "GET"
    assert request_context["request_id"] == "safe-request-1"
    assert request_context["headers"]["authorization"] == "[REDACTED]"
    assert request_context["headers"]["cookie"] == "[REDACTED]"
    assert request_context["headers"]["x-trace-note"] == "safe metadata"
    assert request_context["body"] == "[REDACTED]"
    assert "authorization-secret" not in repr(context)
    assert "cookie-secret" not in repr(context)
    assert "super-secret" not in repr(context)


def test_authenticated_user_id_is_reported_without_user_secrets() -> None:
    tracker = RecordingTracker()
    client = TestClient(_make_app(tracker), raise_server_exceptions=False)

    response = client.get("/authenticated-boom")

    assert response.status_code == 500
    assert tracker.events[0][1]["user_id"] == "user-123"
    assert tracker.events[0][1]["request"]["user_id"] == "user-123"


def test_expected_http_errors_are_not_reported_or_converted() -> None:
    tracker = RecordingTracker()
    client = TestClient(_make_app(tracker))

    response = client.get("/expected")

    assert response.status_code == 409
    assert response.json() == {"detail": "expected conflict"}
    assert tracker.events == []


def test_validation_errors_keep_fastapi_status_and_safe_detail() -> None:
    tracker = RecordingTracker()
    client = TestClient(_make_app(tracker))

    response = client.post("/payload", json={})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "name"]
    assert tracker.events == []


class FakeScope:
    def __init__(self) -> None:
        self.context: dict[str, Any] = {}
        self.user: dict[str, str] | None = None

    def set_context(self, name: str, value: dict[str, Any]) -> None:
        self.context[name] = value

    def set_user(self, value: dict[str, str]) -> None:
        self.user = value


class FakeSentrySDK:
    def __init__(self) -> None:
        self.init_args: dict[str, Any] = {}
        self.scope = FakeScope()
        self.captured: list[BaseException] = []

    def init(self, **kwargs: Any) -> None:
        self.init_args = kwargs

    @contextmanager
    def push_scope(self):
        yield self.scope

    def capture_exception(self, exception: BaseException) -> None:
        self.captured.append(exception)


def test_sentry_adapter_initializes_and_scrubs_provider_context() -> None:
    sdk = FakeSentrySDK()
    tracker = SentryErrorTracker(
        dsn="https://public@example.invalid/1",
        environment="staging",
        release="release-1",
        sample_rate=0.25,
        sdk=sdk,
    )

    tracker.capture_exception(
        RuntimeError("failure"),
        context={
            "request": {
                "route": "/boom",
                "headers": {"Authorization": "secret"},
                "password": "secret",
            },
            "user_id": "user-1",
        },
    )

    assert sdk.init_args["environment"] == "staging"
    assert sdk.init_args["release"] == "release-1"
    assert sdk.scope.context["request"]["headers"]["Authorization"] == "[REDACTED]"
    assert sdk.scope.context["request"]["password"] == "[REDACTED]"
    assert sdk.scope.user == {"id": "user-1"}
    assert len(sdk.captured) == 1
