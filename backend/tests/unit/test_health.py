"""Tests for dependency-aware health checks."""

import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.health import check_dependencies
from app.main import create_app


class FakeConnection:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[str] = []

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, query: object) -> None:
        self.queries.append(str(query))
        if self.error:
            raise self.error


class FakeEngine:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def connect(self) -> FakeConnection:
        return self.connection


class FakeRedis:
    def __init__(self, error: Exception | None = None, delay: float = 0) -> None:
        self.error = error
        self.delay = delay

    async def ping(self) -> bool:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return True


async def _healthy_dependencies() -> dict[str, str]:
    connection = FakeConnection()
    return await check_dependencies(FakeEngine(connection), FakeRedis(), timeout_seconds=0.1)


def test_health_check_reports_both_dependencies_up() -> None:
    statuses = asyncio.run(_healthy_dependencies())

    assert statuses == {"database": "up", "redis": "up"}


def test_health_check_reports_database_down_without_exception_details() -> None:
    statuses = asyncio.run(
        check_dependencies(
            FakeEngine(FakeConnection(RuntimeError("postgres password=secret"))),
            FakeRedis(),
            timeout_seconds=0.1,
        )
    )

    assert statuses == {"database": "down", "redis": "up"}


def test_health_check_reports_redis_down() -> None:
    statuses = asyncio.run(
        check_dependencies(
            FakeEngine(FakeConnection()),
            FakeRedis(error=ConnectionError("redis://:secret@host")),
            timeout_seconds=0.1,
        )
    )

    assert statuses == {"database": "up", "redis": "down"}


def test_health_check_marks_hung_dependency_down_at_timeout() -> None:
    statuses = asyncio.run(
        check_dependencies(
            FakeEngine(FakeConnection()),
            FakeRedis(delay=0.05),
            timeout_seconds=0.001,
        )
    )

    assert statuses == {"database": "up", "redis": "down"}


def test_health_endpoint_returns_503_and_safe_body_when_dependency_is_down() -> None:
    settings = Settings(
        environment="development",
        health_check_timeout_seconds=0.1,
    )
    database = FakeEngine(
        FakeConnection(RuntimeError("postgresql://user:password@db/internal"))
    )

    async def get_redis() -> FakeRedis:
        return FakeRedis(error=ConnectionError("redis password=secret"))

    with (
        patch("app.main.get_settings", return_value=settings),
        patch("app.main.engine", database),
        patch("app.main.get_redis_client", side_effect=get_redis),
    ):
        response = TestClient(create_app()).get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["dependencies"] == {"database": "down", "redis": "down"}
    assert "password" not in response.text
    assert "secret" not in response.text
    assert "Traceback" not in response.text
