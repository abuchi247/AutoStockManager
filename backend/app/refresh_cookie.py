"""HTTP-only refresh cookie handling for browser authentication.

Browsers receive the refresh credential as an HTTP-only, ``Secure``,
``SameSite``-scoped cookie on a narrow path instead of a JSON value that
client-side JavaScript can read. Non-browser clients may keep sending the
credential in the request body during the compatibility window.

Satisfies Requirements: 3.1, 3.3, 3.4, 3.5
"""

from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Response, status

from app.config import Settings


def refresh_cookie_max_age(settings: Settings) -> int:
    """Return the cookie lifetime, matching the refresh token expiry."""
    return settings.jwt_refresh_token_expire_days * 86400


def set_refresh_cookie(
    response: Response,
    refresh_token: str,
    settings: Settings,
) -> None:
    """Store the refresh credential in the configured HTTP-only cookie."""
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=refresh_cookie_max_age(settings),
        httponly=True,
        secure=settings.refresh_cookie_secure_enabled,
        samesite=settings.refresh_cookie_samesite,
        path=settings.refresh_cookie_path,
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    """Expire the refresh cookie using the same attributes it was set with.

    Browsers only replace a cookie when name, path, and security attributes
    match, so deletion must mirror ``set_refresh_cookie``.
    """
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure_enabled,
        samesite=settings.refresh_cookie_samesite,
        path=settings.refresh_cookie_path,
    )


def refresh_cookie_deletion_headers(settings: Settings) -> dict[str, str]:
    """Build a ``Set-Cookie`` header that expires the refresh cookie.

    Error paths raise ``HTTPException`` rather than returning a response, so the
    deletion header is rendered here and attached to the exception.
    """
    probe = Response()
    clear_refresh_cookie(probe, settings)
    return {"set-cookie": probe.headers["set-cookie"]}


def read_refresh_cookie(request: Request, settings: Settings) -> str | None:
    """Return the refresh credential the browser sent, if any."""
    return request.cookies.get(settings.refresh_cookie_name) or None


def resolve_refresh_token(
    request: Request,
    body_token: str | None,
    settings: Settings,
) -> tuple[str | None, bool]:
    """Resolve the refresh credential, preferring the HTTP-only cookie.

    Returns the token and whether it came from the cookie. The cookie wins over
    a body token so a browser cannot be tricked into refreshing an attacker's
    session, while non-browser clients keep the request-body flow.
    """
    cookie_token = read_refresh_cookie(request, settings)
    if cookie_token:
        return cookie_token, True
    return (body_token or None), False


def _normalize_origin(value: str) -> str | None:
    """Reduce a URL or origin to a comparable ``scheme://host[:port]`` form."""
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def trusted_origins(request: Request, settings: Settings) -> set[str]:
    """Origins allowed to make cookie-authenticated state changes."""
    candidates = [*settings.cors_origins, settings.frontend_base_url]
    origins = {
        normalized
        for normalized in (_normalize_origin(value) for value in candidates)
        if normalized is not None
    }

    # Deployments that serve the UI and API from one origin do not need to list
    # that origin in the CORS configuration.
    host = request.headers.get("host")
    if host:
        origins.add(f"{request.url.scheme.lower()}://{host.lower()}")

    return origins


def assert_trusted_origin(request: Request, settings: Settings) -> None:
    """Reject cross-site cookie-authenticated state changes (CSRF defense).

    A ``SameSite`` cookie already prevents most cross-site submission, so this
    check is defense in depth for browsers that declare an origin. Requests with
    no ``Origin``/``Referer`` header are not browser cross-site submissions and
    are left to normal token validation.
    """
    declared = request.headers.get("origin") or request.headers.get("referer")
    if not declared:
        return

    origin = _normalize_origin(declared)
    if origin is None or origin not in trusted_origins(request, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin is not allowed for cookie authentication",
        )
