"""Security headers middleware for HTTP response hardening.

Adds security headers to all responses:
- Content-Security-Policy: default-src 'self'
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Strict-Transport-Security: max-age=31536000; includeSubDomains
- X-XSS-Protection: 1; mode=block

Satisfies Requirements:
- 17.7: Enforce HTTPS in production (HSTS header)
- 17.8: Set secure HTTP headers (CSP, X-Content-Type-Options, X-Frame-Options, HSTS)
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that injects security headers into every HTTP response.

    These headers protect against common web vulnerabilities including
    clickjacking, MIME-type sniffing, cross-site scripting, and
    protocol downgrade attacks.
    """

    SECURITY_HEADERS = {
        "Content-Security-Policy": "default-src 'self'",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-XSS-Protection": "1; mode=block",
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request and add security headers to the response.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response with security headers appended.
        """
        response = await call_next(request)

        for header_name, header_value in self.SECURITY_HEADERS.items():
            response.headers[header_name] = header_value

        return response
