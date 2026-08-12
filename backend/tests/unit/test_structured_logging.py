"""Structured logging configuration contract.

Requirement 5 requires JSON log records carrying timestamp, level, logger name,
message, and request ID, an environment-driven verbosity setting, and redaction
of password/token/secret fields before logging.

Validates: Requirements 1.4, 5.1, 5.3, 5.4
"""

import io
import json
import logging
from collections.abc import Iterator

import pytest

from app.config import Settings
from app.logging_config import (
    REDACTED,
    DevelopmentLogFormatter,
    JSONLogFormatter,
    configure_logging,
    redact_text,
    redact_value,
    resolve_log_level,
)
from app.middleware.request_id import request_id_var


DATABASE_URL = "postgresql+asyncpg://erp_app:sup3r-s3cret@db.internal:5432/erp"
JWT_VALUE = (
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwidHlwZSI6InJlc2V0In0.c2lnbmF0dXJlLXZhbHVl"
)


@pytest.fixture(autouse=True)
def restore_root_logger() -> Iterator[None]:
    """Keep logging changes from leaking between tests."""
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    yield
    for handler in list(root_logger.handlers):
        if handler not in original_handlers:
            root_logger.removeHandler(handler)
    for handler in original_handlers:
        if handler not in root_logger.handlers:
            root_logger.addHandler(handler)
    root_logger.setLevel(original_level)


def _settings(**overrides) -> Settings:
    """Build settings, defaulting to a JSON-emitting (non-development) environment."""
    defaults = {
        "environment": "staging",
        "app_name": "Auto Spare Parts ERP",
        "jwt_secret_key": "a" * 32,
        "postgres_password": "a-real-database-password",
    }
    merged = {**defaults, **overrides}
    # Supply production-required fields when building a production Settings object
    # so tests that exercise production log behaviour don't fail on config validation.
    if merged.get("environment") == "production":
        merged.setdefault("smtp_host", "smtp.example.com")
        merged.setdefault("smtp_from_email", "no-reply@example.com")
        merged.setdefault("cors_origins", ["https://app.example.com"])
    return Settings(**merged)


def _emit(
    settings: Settings,
    message: str,
    *,
    level: int = logging.INFO,
    extra: dict | None = None,
) -> str:
    """Configure logging against a buffer and return the emitted output."""
    buffer = io.StringIO()
    configure_logging(settings, stream=buffer)
    logging.getLogger("app.test").log(level, message, extra=extra or {})
    return buffer.getvalue()


def _emit_json(settings: Settings, message: str, **kwargs) -> dict:
    output = _emit(settings, message, **kwargs)
    assert output.strip(), "no log record was emitted"
    return json.loads(output.strip().splitlines()[-1])


def test_settings_expose_log_verbosity() -> None:
    """Verbosity is configured per environment through settings."""
    assert "log_level" in Settings.model_fields


def test_structured_logging_module_is_available() -> None:
    """A JSON formatter with secret redaction must exist and be installable."""
    from app.logging_config import configure_logging  # noqa: F401


class TestRecordFields:
    """Requirement 5.1: JSON records carry consistent correlation fields."""

    def test_json_record_contains_standard_fields(self) -> None:
        record = _emit_json(_settings(environment="production", jwt_secret_key="a" * 32), "database_migrations_started")

        assert record["level"] == "INFO"
        assert record["logger"] == "app.test"
        assert record["message"] == "database_migrations_started"
        assert record["service"] == "Auto Spare Parts ERP"
        assert record["environment"] == "production"
        assert record["timestamp"].endswith("Z")
        assert "request_id" in record

    def test_request_id_from_context_is_included(self) -> None:
        token = request_id_var.set("req-1234")
        try:
            record = _emit_json(_settings(), "background_job_outcome")
        finally:
            request_id_var.reset(token)

        assert record["request_id"] == "req-1234"
        assert record["trace_id"] == "req-1234"

    def test_extra_fields_are_preserved(self) -> None:
        record = _emit_json(
            _settings(),
            "background_job_outcome",
            extra={"job_name": "send_password_reset", "attempt": 2},
        )

        assert record["job_name"] == "send_password_reset"
        assert record["attempt"] == 2

    def test_exception_text_is_included(self) -> None:
        buffer = io.StringIO()
        configure_logging(_settings(), stream=buffer)
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            logging.getLogger("app.test").exception("job_failed")

        record = json.loads(buffer.getvalue().strip().splitlines()[-1])
        assert "RuntimeError: boom" in record["exception"]

    def test_development_output_is_human_readable(self) -> None:
        token = request_id_var.set("req-dev")
        try:
            output = _emit(_settings(environment="development"), "cache_warmed")
        finally:
            request_id_var.reset(token)

        assert output.startswith("2")  # ISO timestamp
        assert "INFO" in output
        assert "app.test" in output
        assert "[req-dev]" in output
        assert "cache_warmed" in output


class TestLogVerbosity:
    """Requirement 5.3: verbosity comes from settings, per environment."""

    def test_development_defaults_to_debug(self) -> None:
        assert resolve_log_level(_settings(environment="development")) == logging.DEBUG

    def test_production_defaults_to_info(self) -> None:
        settings = _settings(environment="production", jwt_secret_key="a" * 32)
        assert resolve_log_level(settings) == logging.INFO

    def test_explicit_setting_overrides_environment_default(self) -> None:
        settings = _settings(environment="development", log_level="warning")
        assert resolve_log_level(settings) == logging.WARNING

    def test_unrecognized_level_falls_back_to_environment_default(self) -> None:
        settings = _settings(environment="development", log_level="not-a-level")
        assert resolve_log_level(settings) == logging.DEBUG

    def test_info_records_are_emitted_after_configuration(self) -> None:
        settings = _settings(environment="production", jwt_secret_key="a" * 32)
        output = _emit(settings, "database_migrations_started")

        assert "database_migrations_started" in output

    def test_records_below_the_level_are_dropped(self) -> None:
        settings = _settings(environment="production", jwt_secret_key="a" * 32)
        output = _emit(settings, "verbose_detail", level=logging.DEBUG)

        assert output == ""

    def test_configuration_is_idempotent(self) -> None:
        settings = _settings()
        configure_logging(settings, stream=io.StringIO())
        configure_logging(settings, stream=io.StringIO())

        structured = [
            handler
            for handler in logging.getLogger().handlers
            if handler.get_name() == "asm_structured"
        ]
        assert len(structured) == 1


class TestRedaction:
    """Requirements 1.4 and 5.4: secrets never reach a log handler."""

    @pytest.mark.parametrize(
        "field",
        [
            "password",
            "new_password",
            "authorization",
            "Authorization",
            "cookie",
            "set-cookie",
            "access_token",
            "refresh_token",
            "reset_token",
            "jwt_secret_key",
            "database_url",
            "error_tracker_dsn",
            "api_key",
            "X-API-Key",
            "client_secret",
        ],
    )
    def test_sensitive_extra_fields_are_redacted(self, field: str) -> None:
        secret = "sup3r-s3cret-value"
        record = _emit_json(_settings(), "auth_event", extra={field: secret})

        assert secret not in json.dumps(record)
        assert record[field] == REDACTED

    def test_nested_sensitive_values_are_redacted(self) -> None:
        record = _emit_json(
            _settings(),
            "request_context",
            extra={
                "request": {
                    "headers": {
                        "authorization": "Bearer abc.def.ghi",
                        "cookie": "asm_refresh=abc123",
                        "content-type": "application/json",
                    },
                    "body": {"email": "user@example.com", "password": "hunter2"},
                }
            },
        )

        request = record["request"]
        assert request["headers"]["authorization"] == REDACTED
        assert request["headers"]["cookie"] == REDACTED
        assert request["headers"]["content-type"] == "application/json"
        assert request["body"]["password"] == REDACTED
        assert request["body"]["email"] == "user@example.com"
        serialized = json.dumps(record)
        assert "hunter2" not in serialized
        assert "abc123" not in serialized

    def test_database_url_credentials_are_redacted_in_messages(self) -> None:
        record = _emit_json(_settings(), f"connecting to {DATABASE_URL}")

        assert "sup3r-s3cret" not in json.dumps(record)
        assert REDACTED in record["message"]
        # The non-secret parts stay searchable for operators.
        assert "db.internal:5432" in record["message"]

    def test_jwt_values_are_redacted_anywhere_in_a_message(self) -> None:
        record = _emit_json(_settings(), f"password reset link token {JWT_VALUE}")

        assert JWT_VALUE not in json.dumps(record)
        assert REDACTED in record["message"]

    @pytest.mark.parametrize(
        "message",
        [
            "login payload password=hunter2",
            'body {"password": "hunter2"}',
            "reset_token=hunter2",
            "Authorization: Bearer hunter2",
            "cookie: asm_refresh=hunter2",
            "SMTP_PASSWORD='hunter2'",
        ],
    )
    def test_credential_shaped_message_text_is_redacted(self, message: str) -> None:
        record = _emit_json(_settings(), message)

        assert "hunter2" not in json.dumps(record)

    def test_secret_in_positional_argument_is_redacted(self) -> None:
        buffer = io.StringIO()
        configure_logging(_settings(), stream=buffer)
        logging.getLogger("app.test").info("database url %s", DATABASE_URL)

        assert "sup3r-s3cret" not in buffer.getvalue()

    def test_development_output_redacts_secrets(self) -> None:
        output = _emit(
            _settings(environment="development"),
            f"connecting to {DATABASE_URL}",
            extra={"password": "hunter2"},
        )

        assert "sup3r-s3cret" not in output
        assert "hunter2" not in output
        assert REDACTED in output

    def test_redact_value_handles_sequences(self) -> None:
        result = redact_value([{"token": "abc"}, "password=xyz"])

        assert result[0]["token"] == REDACTED
        assert "xyz" not in result[1]

    def test_redact_text_preserves_non_secret_content(self) -> None:
        assert redact_text("sale_confirmed sale_id=42") == "sale_confirmed sale_id=42"

    def test_formatters_share_redaction_behavior(self) -> None:
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="url %s",
            args=(DATABASE_URL,),
            exc_info=None,
        )
        for formatter in (
            JSONLogFormatter(service="svc", environment="production"),
            DevelopmentLogFormatter(service="svc", environment="development"),
        ):
            assert "sup3r-s3cret" not in formatter.format(record)
