"""Rate limiting middleware using slowapi with Redis backend.

Implements tiered rate limiting:
- 100 requests/minute for authenticated users (keyed by user_id)
- 20 requests/minute for unauthenticated users (keyed by IP address)

Returns HTTP 429 Too Many Requests when limits are exceeded.

Satisfies Requirement 17.2: Rate limiting 100/min authenticated, 20/min unauthenticated.
"""

from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings


def get_rate_limit_key(request: Request) -> str:
    """Determine the rate limit key based on authentication status.

    For authenticated requests (valid Bearer token), keys by user_id
    to allow the higher 100 req/min limit. For unauthenticated requests,
    keys by client IP for the lower 20 req/min limit.

    Args:
        request: The incoming Starlette/FastAPI request.

    Returns:
        A string key for rate limiting: "user:{user_id}" or the client IP.
    """
    settings = get_settings()
    auth_header = request.headers.get("authorization", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except JWTError:
            pass

    # Fall back to IP-based limiting for unauthenticated requests
    return get_remote_address(request)


def _dynamic_rate_limit(request: Request) -> str:
    """Return the appropriate rate limit string based on authentication.

    Authenticated users get 100/minute, unauthenticated get 20/minute.

    Args:
        request: The incoming request.

    Returns:
        Rate limit string in slowapi format (e.g., "100/minute").
    """
    settings = get_settings()
    auth_header = request.headers.get("authorization", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            if payload.get("sub"):
                return f"{settings.rate_limit_authenticated}/minute"
        except JWTError:
            pass

    return f"{settings.rate_limit_unauthenticated}/minute"


def create_rate_limiter() -> Limiter:
    """Create and configure the slowapi Limiter instance.

    Uses Redis as the storage backend for distributed rate limiting.
    The key function distinguishes authenticated vs unauthenticated
    requests for differentiated rate limits.

    Returns:
        Configured slowapi Limiter instance.
    """
    settings = get_settings()

    limiter = Limiter(
        key_func=get_rate_limit_key,
        default_limits=[f"{settings.rate_limit_unauthenticated}/minute"],
        storage_uri=settings.redis_url,
    )

    return limiter


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors.

    Returns a JSON response with HTTP 429 status and retry information.

    Args:
        request: The request that exceeded the rate limit.
        exc: The RateLimitExceeded exception from slowapi.

    Returns:
        JSONResponse with 429 status code.
    """
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please try again later.",
            "retry_after": str(exc.detail),
        },
    )
