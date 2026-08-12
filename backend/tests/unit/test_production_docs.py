"""Tests for protected production API documentation access."""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.middleware.auth import get_current_user
from app.models.user import UserRole


@pytest.fixture
def production_settings() -> Settings:
    """Return production settings with non-placeholder credentials."""
    return Settings(
        environment="production",
        jwt_secret_key="production-test-secret-" + "x" * 32,
        postgres_password="production-database-password",
        database_url="postgresql+asyncpg://postgres:unused@db:5432/erp",
        smtp_host="smtp.example.com",
        smtp_from_email="no-reply@example.com",
        cors_origins=["https://app.example.com"],
    )


@pytest.fixture
def production_app(monkeypatch, production_settings):
    """Create a production app without starting external dependencies."""
    monkeypatch.setattr("app.main.get_settings", lambda: production_settings)
    return create_app()


async def request(app, method: str, path: str):
    """Make an ASGI request without invoking the application lifespan."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path)


@pytest.mark.asyncio
async def test_production_disables_public_docs_and_schema(production_app):
    """The standard documentation and OpenAPI URLs are absent in production."""
    assert production_app.docs_url is None
    assert production_app.redoc_url is None
    assert production_app.openapi_url is None

    assert (await request(production_app, "GET", "/docs")).status_code == 404
    assert (await request(production_app, "GET", "/redoc")).status_code == 404
    assert (await request(production_app, "GET", "/openapi.json")).status_code == 404


@pytest.mark.asyncio
async def test_production_docs_require_authentication(production_app):
    """Both the documentation page and schema reject unauthenticated requests."""
    assert (await request(production_app, "GET", "/internal/docs")).status_code == 401
    assert (
        await request(production_app, "GET", "/internal/openapi.json")
    ).status_code == 401


@pytest.mark.asyncio
async def test_production_docs_require_admin_role(production_app):
    """Authenticated non-admin users cannot access production documentation."""

    async def current_manager():
        return SimpleNamespace(role=UserRole.MANAGER.value, is_active=True)

    production_app.dependency_overrides[get_current_user] = current_manager
    try:
        assert (await request(production_app, "GET", "/internal/docs")).status_code == 403
        assert (
            await request(production_app, "GET", "/internal/openapi.json")
        ).status_code == 403
    finally:
        production_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_production_admin_can_access_docs_and_schema(production_app):
    """An authenticated Admin can use the protected documentation mechanism."""

    async def current_admin():
        return SimpleNamespace(role=UserRole.ADMIN.value, is_active=True)

    production_app.dependency_overrides[get_current_user] = current_admin
    try:
        docs_response = await request(production_app, "GET", "/internal/docs")
        schema_response = await request(
            production_app, "GET", "/internal/openapi.json"
        )
    finally:
        production_app.dependency_overrides.clear()

    assert docs_response.status_code == 200
    assert "swagger-ui" in docs_response.text
    assert schema_response.status_code == 200
    assert schema_response.json()["openapi"].startswith("3.")


@pytest.mark.asyncio
async def test_development_keeps_standard_docs_enabled(monkeypatch):
    """Local development retains FastAPI's normal documentation URLs."""
    settings = Settings(environment="development")
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    app = create_app()

    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"
    assert not any(
        getattr(route, "path", None) == "/internal/openapi.json"
        for route in app.routes
    )
