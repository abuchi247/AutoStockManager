"""FastAPI application factory."""

import asyncio
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import close_db, engine, init_db
from app.health import check_dependencies
from app.error_tracking import create_error_tracker
from app.exception_handlers import install_exception_handlers
from app.initial_admin import ensure_initial_admin
from app.initial_data import ensure_default_categories
from app.logging_config import configure_logging
from app.middleware.rate_limit import create_rate_limiter, rate_limit_exceeded_handler
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.request_size import RequestSizeMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.telemetry import TelemetryMiddleware
from app.telemetry import create_telemetry
from app.middleware.auth import require_roles
from app.models.user import UserRole
from app.routers.audits import router as audits_router
from app.routers.auth import router as auth_router
from app.routers.barcodes import router as barcodes_router
from app.routers.business_settings import router as business_settings_router
from app.routers.categories import router as categories_router
from app.routers.credit import router as credit_router
from app.routers.dashboard import router as dashboard_router
from app.routers.invoices import router as invoices_router
from app.routers.notifications import router as notifications_router
from app.routers.spare_parts import router as spare_parts_router
from app.routers.stock import router as stock_router
from app.routers.reports import router as reports_router
from app.routers.transfers import router as transfers_router
from app.routers.users import router as users_router
from app.routers.customers import router as customers_router
from app.routers.locations import router as locations_router
from app.routers.suppliers import router as suppliers_router
from app.routers.purchases import router as purchases_router
from app.routers.sales import router as sales_router
from app.services.background_jobs import close_arq_pool
from app.services.session_service import close_redis_client, get_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    await init_db()
    await get_redis_client()  # Initialize Redis connection
    await ensure_initial_admin()          # Create admin if no users exist
    await ensure_default_categories()     # Seed categories if table is empty
    yield
    # Shutdown
    await close_arq_pool()
    await close_redis_client()
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Uses the application factory pattern so the app can be configured
    differently for testing, development, and production environments.
    """
    settings = get_settings()

    # Install structured logging before anything else so startup events
    # (migrations, dependency checks, job outcomes) are actually emitted.
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        # FastAPI exposes /openapi.json independently from its documentation
        # pages. Disable that default route in production so disabling /docs
        # and /redoc cannot leave the schema publicly reachable.
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )

    if settings.environment == "production":
        admin_docs = Depends(require_roles(UserRole.ADMIN))

        @app.get(
            "/internal/docs",
            include_in_schema=False,
            dependencies=[admin_docs],
        )
        async def protected_docs():
            """Serve Swagger UI only to authenticated administrators."""
            return get_swagger_ui_html(
                openapi_url="/internal/openapi.json",
                title=f"{settings.app_name} - Internal API documentation",
            )

        @app.get(
            "/internal/openapi.json",
            include_in_schema=False,
            dependencies=[admin_docs],
        )
        async def protected_openapi():
            """Serve the OpenAPI schema only to authenticated administrators."""
            return JSONResponse(content=app.openapi())

    # Global exception handling reports unexpected failures without exposing
    # request data. Expected HTTP and validation errors retain their status and
    # response shape.
    install_exception_handlers(app, tracker=create_error_tracker(settings))

    # Telemetry adapter for metrics, tracing, and performance monitoring.
    create_telemetry(
        environment=settings.environment,
        enabled=settings.telemetry_enabled,
    )

    # Rate limiting (slowapi)
    limiter = create_rate_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Enforce both declared and streamed request body sizes. This is added
    # immediately inside request-ID middleware so rejected responses still
    # receive the normal X-Request-ID response header.
    app.add_middleware(
        RequestSizeMiddleware,
        max_body_size=settings.max_request_body_bytes,
    )

    # Telemetry middleware records request metrics and propagates trace IDs.
    # It sits inside request-ID middleware so both IDs are available.
    app.add_middleware(TelemetryMiddleware)

    # Request correlation must wrap the complete HTTP stack so that request
    # IDs are attached to normal and handled-error responses alike.
    app.add_middleware(RequestIDMiddleware)

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        # Client creation is normally local and non-blocking, but bound it as
        # well so a broken client factory cannot make readiness hang.
        try:
            redis_client = await asyncio.wait_for(
                get_redis_client(),
                timeout=settings.health_check_timeout_seconds,
            )
        except Exception:
            redis_client = None

        dependencies = await check_dependencies(
            database_engine=engine,
            redis_client=redis_client,
            timeout_seconds=settings.health_check_timeout_seconds,
        )
        healthy = all(status == "up" for status in dependencies.values())
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "healthy" if healthy else "unhealthy",
                "version": settings.app_version,
                "commit": os.environ.get(
                    "RAILWAY_GIT_COMMIT_SHA",
                    os.environ.get("GIT_COMMIT_SHA", "local"),
                ),
                "dependencies": dependencies,
            },
        )

    # API version prefix
    @app.get("/api/v1/status", tags=["Status"])
    async def api_status():
        import os
        return {
            "status": "operational",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "commit": os.environ.get("RAILWAY_GIT_COMMIT_SHA", os.environ.get("GIT_COMMIT_SHA", "local")),
        }

    # Register routers
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(categories_router)
    app.include_router(spare_parts_router)
    app.include_router(stock_router)
    app.include_router(transfers_router)
    app.include_router(customers_router)
    app.include_router(suppliers_router)
    app.include_router(locations_router)
    app.include_router(credit_router)
    app.include_router(sales_router)
    app.include_router(purchases_router)
    app.include_router(barcodes_router)
    app.include_router(audits_router)
    app.include_router(reports_router)
    app.include_router(dashboard_router)
    app.include_router(invoices_router)
    app.include_router(notifications_router)
    app.include_router(business_settings_router)

    return app


# Application instance for uvicorn
app = create_app()
