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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    await init_db()
    yield
    # Shutdown
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

    return app


# Application instance for uvicorn
app = create_app()
