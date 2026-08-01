"""Structured logging configuration with secret redaction.

The application emits machine-parseable JSON log records outside local
development so operators can search and correlate events by request ID. Every
record carries the same core fields (timestamp, level, logger, message,
service, environment, request ID) and any additional ``extra`` fields supplied
by the caller.

Nothing that reaches a handler is trusted to be free of credentials: record
messages, arguments, and extra fields are redacted before they are emitted.
Redaction covers authorization headers, cookies, passwords, JWTs (including
password-reset tokens), API keys, DSNs, and credentials embedded in database
URLs. This is deliberately independent from the error tracker's own scrubbing
(``app.error_tracking``) so a failure or misconfiguration of one does not leak
secrets through the other.

Validates: Requirements 1.4, 5.1, 5.3, 5.4
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import IO, Any

from app.config import Settings, get_settings
from app.middleware.request_id import request_id_var

REDACTED = "[REDACTED]"

VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# Field/key fragments whose values must never be emitted. Matching is done on a
# normalized name so ``X-API-Key``, ``api_key``, and ``apiKey`` all match.
_SENSITIVE_NAME_PARTS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "api_key",
    "apikey",
    "database_url",
    "dsn",
    "jwt",
    "private_key",
    "session_key",
)

# Key names used in free-text messages, e.g. ``password=hunter2`` or
# ``{"reset_token": "..."}``.
_TEXT_KEY_FRAGMENT = (
    r"(?:password|passwd|secret|token|credential|jwt|dsn|cookie"
    r"|authorization|api[_-]?key|apikey|database_url)"
)

_URL_CREDENTIALS_PATTERN = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)(?P<user>[^:/?#\s@]+):(?P<password>[^@/?#\s]*)@"
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-=+/]+")
_JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*"
)
_QUOTED_KEY_VALUE_PATTERN = re.compile(
    rf'(?i)(?P<prefix>"[A-Za-z0-9_\-]*{_TEXT_KEY_FRAGMENT}[A-Za-z0-9_\-]*"\s*:\s*)"[^"]*"'
)
_BARE_KEY_VALUE_PATTERN = re.compile(
    rf"(?i)(?P<prefix>\b[A-Za-z0-9_\-]*{_TEXT_KEY_FRAGMENT}[A-Za-z0-9_\-]*\b\s*[=:]\s*)"
    r"(?!\[REDACTED)(?P<value>\"[^\"]*\"|'[^']*'|(?:bearer\s+)?[^\s,;&)\]}]+)"
)

# LogRecord attributes that are not caller-supplied context.
_RESERVED_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
        # Injected by RequestContextFilter and rendered as top-level fields.
        "request_id",
        "trace_id",
    }
)


def is_sensitive_name(name: object) -> bool:
    """Return whether a field name is known to carry a credential."""

    normalized = str(name).lower().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in _SENSITIVE_NAME_PARTS)


def redact_text(text: str) -> str:
    """Remove credentials that appear inside a free-text log message."""

    redacted = _URL_CREDENTIALS_PATTERN.sub(
        rf"\g<scheme>\g<user>:{REDACTED}@", text
    )
    redacted = _QUOTED_KEY_VALUE_PATTERN.sub(rf'\g<prefix>"{REDACTED}"', redacted)
    # Runs before the standalone bearer rule so ``Authorization: Bearer x``
    # collapses to a single redaction instead of two.
    redacted = _BARE_KEY_VALUE_PATTERN.sub(rf"\g<prefix>{REDACTED}", redacted)
    redacted = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", redacted)
    redacted = _JWT_PATTERN.sub(REDACTED, redacted)
    return redacted


def redact_value(value: Any) -> Any:
    """Recursively redact sensitive keys and credential-shaped strings."""

    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if is_sensitive_name(key) else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return redact_text(str(value))


def _current_trace_id() -> str | None:
    """Return the active trace ID without importing telemetry at module level.

    ``app.telemetry`` imports the request-ID middleware, and application modules
    import this one during startup. The import is kept local so logging cannot
    introduce an import cycle.
    """

    try:
        from app.telemetry import trace_id_var
    except Exception:  # pragma: no cover - telemetry is always importable
        return None
    return trace_id_var.get()


class RequestContextFilter(logging.Filter):
    """Attach the request-scoped correlation IDs to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id_var.get()
        if getattr(record, "trace_id", None) is None:
            record.trace_id = _current_trace_id() or record.request_id
        return True


class _BaseRedactingFormatter(logging.Formatter):
    """Shared field extraction and redaction for both output formats."""

    def __init__(self, *, service: str, environment: str) -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def _message(self, record: logging.LogRecord) -> str:
        try:
            message = record.getMessage()
        except Exception:
            # A bad format string must not lose the event entirely.
            message = str(record.msg)
        return redact_text(message)

    def _extras(self, record: logging.LogRecord) -> dict[str, Any]:
        return {
            key: REDACTED if is_sensitive_name(key) else redact_value(value)
            for key, value in record.__dict__.items()
            if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_")
        }

    def _timestamp(self, record: logging.LogRecord) -> str:
        moment = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _exception_text(self, record: logging.LogRecord) -> str | None:
        if record.exc_info:
            return redact_text(self.formatException(record.exc_info))
        if record.exc_text:
            return redact_text(record.exc_text)
        return None

    def _fields(self, record: logging.LogRecord) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "timestamp": self._timestamp(record),
            "level": record.levelname,
            "logger": record.name,
            "message": self._message(record),
            "service": self.service,
            "environment": self.environment,
            "request_id": getattr(record, "request_id", None),
        }
        trace_id = getattr(record, "trace_id", None)
        if trace_id is not None:
            fields["trace_id"] = trace_id
        return fields


class JSONLogFormatter(_BaseRedactingFormatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload = self._fields(record)
        payload.update(self._extras(record))

        exception_text = self._exception_text(record)
        if exception_text is not None:
            payload["exception"] = exception_text
        if record.stack_info:
            payload["stack"] = redact_text(self.formatStack(record.stack_info))

        return json.dumps(payload, default=lambda value: redact_text(str(value)))


class DevelopmentLogFormatter(_BaseRedactingFormatter):
    """Emit a compact, human-readable line for local development."""

    def format(self, record: logging.LogRecord) -> str:
        fields = self._fields(record)
        request_id = fields["request_id"] or "-"
        line = (
            f"{fields['timestamp']} {fields['level']:<8} {fields['logger']} "
            f"[{request_id}] {fields['message']}"
        )

        extras = self._extras(record)
        if extras:
            line += " " + " ".join(
                f"{key}={value}" for key, value in sorted(extras.items())
            )

        exception_text = self._exception_text(record)
        if exception_text is not None:
            line += "\n" + exception_text
        if record.stack_info:
            line += "\n" + redact_text(self.formatStack(record.stack_info))

        return line


def resolve_log_level(settings: Settings) -> int:
    """Return the numeric log level for the configured environment."""

    configured = settings.log_level
    if configured:
        candidate = str(configured).strip().upper()
        if candidate in VALID_LOG_LEVELS:
            return logging.getLevelName(candidate)  # type: ignore[return-value]
    return logging.DEBUG if settings.environment == "development" else logging.INFO


def build_formatter(settings: Settings) -> logging.Formatter:
    """Build the JSON or development formatter for the environment."""

    formatter_class = (
        DevelopmentLogFormatter
        if settings.environment == "development"
        else JSONLogFormatter
    )
    return formatter_class(
        service=settings.app_name,
        environment=settings.environment,
    )


def configure_logging(
    settings: Settings | None = None,
    *,
    stream: IO[str] | None = None,
) -> logging.Handler:
    """Install the structured logging handler on the root logger.

    Calling this more than once replaces the previously installed handler
    instead of duplicating output. Handlers installed by other tooling (such as
    the test runner's capture handler) are left in place.
    """

    settings = settings or get_settings()

    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(build_formatter(settings))
    handler.addFilter(RequestContextFilter())
    handler.set_name("asm_structured")

    root_logger = logging.getLogger()
    for existing in list(root_logger.handlers):
        if existing.get_name() == "asm_structured":
            root_logger.removeHandler(existing)
            existing.close()

    root_logger.addHandler(handler)
    root_logger.setLevel(resolve_log_level(settings))

    # Uvicorn installs its own handlers; route its records through ours so
    # every line shares one format and correlation context.
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    return handler
