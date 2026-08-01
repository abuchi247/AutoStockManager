"""Cookie-based refresh authentication contract.

Requirement 3 (Token Storage and Exposure) requires the refresh token to be an
HTTP-only cookie that ``/api/v1/auth/refresh`` and ``/api/v1/auth/logout``
accept without a JSON body, with the request-body flow retained only for
non-browser clients.

Validates: Requirements 3.1, 3.4, 3.5
"""

import pytest

from app.config import Settings
from app.main import create_app
from app.schemas.auth import TokenResponse


def _operation(schema: dict, path: str) -> dict:
    return schema["paths"][path]["post"]


@pytest.fixture(scope="module")
def openapi_schema() -> dict:
    return create_app().openapi()


def test_refresh_does_not_require_a_json_body(openapi_schema: dict) -> None:
    """Browsers refresh with the HTTP-only cookie and no request body."""
    operation = _operation(openapi_schema, "/api/v1/auth/refresh")
    assert operation.get("requestBody", {}).get("required") is not True


def test_logout_does_not_require_a_json_body(openapi_schema: dict) -> None:
    """Logout clears the cookie the browser sent, without a body token."""
    operation = _operation(openapi_schema, "/api/v1/auth/logout")
    assert operation.get("requestBody", {}).get("required") is not True


def test_token_response_does_not_expose_refresh_credentials() -> None:
    """Refresh credentials must never be readable by client-side JavaScript."""
    assert "refresh_token" not in TokenResponse.model_fields


def test_settings_define_refresh_cookie_attributes() -> None:
    """Cookie attributes are configuration, not hard-coded per environment."""
    fields = Settings.model_fields
    assert "refresh_cookie_name" in fields
    assert "refresh_cookie_path" in fields
    assert "refresh_cookie_samesite" in fields
    assert "refresh_cookie_secure" in fields
