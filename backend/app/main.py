"""FastAPI application factory."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import close_db, init_db
from app.middleware.rate_limit import create_rate_limiter, rate_limit_exceeded_handler
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers.audits import router as audits_router
from app.routers.auth import router as auth_router
from app.routers.barcodes import router as barcodes_router
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
from app.services.session_service import close_redis_client, get_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    await init_db()
    await get_redis_client()  # Initialize Redis connection
    yield
    # Shutdown
    await close_redis_client()
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Uses the application factory pattern so the app can be configured
    differently for testing, development, and production environments.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
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
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "version": settings.app_version}

    # API version prefix
    @app.get("/api/v1/status", tags=["Status"])
    async def api_status():
        return {
            "status": "operational",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
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

    return app


# Application instance for uvicorn
app = create_app()
