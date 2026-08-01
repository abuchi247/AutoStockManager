"""Unit and integration-style coverage for Redis-backed ARQ jobs."""

from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.services import background_jobs
from app.services.background_jobs import (
    PASSWORD_RESET_EMAIL_JOB,
    REPORT_GENERATION_JOB,
    ConsoleEmailSender,
    PermanentJobError,
    Retry,
    TransientJobError,
    enqueue_job,
    generate_report,
    password_reset_email,
    retry_delay,
)


def settings() -> Settings:
    return Settings(
        jwt_secret_key="test-secret-key-for-background-jobs",
        database_url="postgresql+asyncpg://test:test@localhost/test",
        job_max_tries=3,
        job_base_backoff_seconds=2,
        job_max_backoff_seconds=5,
    )


@pytest.mark.asyncio
async def test_enqueue_returns_opaque_id_and_uses_arq_contract(monkeypatch):
    pool = AsyncMock()
    background_jobs._arq_pool = pool
    try:
        job_id = await enqueue_job(
            PASSWORD_RESET_EMAIL_JOB,
            {"recipient": "user@example.com", "reset_url": "https://app/reset?token=secret"},
            settings(),
        )
    finally:
        background_jobs._arq_pool = None

    assert job_id
    pool.enqueue_job.assert_awaited_once()
    call_args, call_kwargs = pool.enqueue_job.await_args
    assert call_args == (PASSWORD_RESET_EMAIL_JOB,)
    assert call_kwargs["_job_id"] == job_id
    assert call_kwargs["recipient"] == "user@example.com"
    assert call_kwargs["reset_url"] == "https://app/reset?token=secret"
    # Trace context is propagated so job logs correlate with the request that
    # enqueued them. Outside a request both values are unset.
    assert call_kwargs["_propagated_request_id"] is None
    assert call_kwargs["_propagated_trace_id"] is None


@pytest.mark.asyncio
async def test_password_reset_success_logs_safe_job_outcome(caplog):
    caplog.set_level("INFO")
    sender = AsyncMock()
    ctx = {"job_id": "job-success", "job_try": 1, "settings": settings(), "email_sender": sender}

    await password_reset_email(
        ctx,
        recipient="user@example.com",
        reset_url="https://app/reset?token=secret-reset-token",
    )

    sender.send_password_reset.assert_awaited_once()
    outcome = next(record for record in caplog.records if record.message == "background_job_outcome")
    assert outcome.job_id == "job-success"
    assert outcome.job_name == PASSWORD_RESET_EMAIL_JOB
    assert outcome.attempt == 1
    assert outcome.outcome == "success"
    assert "secret-reset-token" not in caplog.text


@pytest.mark.asyncio
async def test_transient_failure_retries_with_exponential_backoff(caplog):
    caplog.set_level("INFO")
    sender = AsyncMock()
    sender.send_password_reset.side_effect = TransientJobError()
    ctx = {"job_id": "job-retry", "job_try": 2, "settings": settings(), "email_sender": sender}

    with pytest.raises(Retry) as raised:
        await password_reset_email(ctx, recipient="user@example.com", reset_url="https://app/reset?token=x")

    assert raised.value.__dict__["defer_score"] == 4000
    outcome = next(record for record in caplog.records if record.message == "background_job_outcome")
    assert outcome.outcome == "retry"
    assert retry_delay(3, settings()) == 5


@pytest.mark.asyncio
async def test_transient_failure_at_limit_is_terminal(caplog):
    caplog.set_level("INFO")
    sender = AsyncMock()
    sender.send_password_reset.side_effect = TransientJobError()
    job_settings = settings()
    ctx = {"job_id": "job-terminal", "job_try": 3, "settings": job_settings, "email_sender": sender}

    with pytest.raises(TransientJobError):
        await password_reset_email(ctx, recipient="user@example.com", reset_url="https://app/reset?token=x")

    outcome = next(record for record in caplog.records if record.message == "background_job_outcome")
    assert outcome.outcome == "terminal_failure"


@pytest.mark.asyncio
async def test_unknown_failure_is_terminal_and_does_not_log_exception(caplog):
    caplog.set_level("INFO")
    sender = AsyncMock()
    sender.send_password_reset.side_effect = RuntimeError("contains secret-reset-token")
    ctx = {"job_id": "job-error", "job_try": 1, "settings": settings(), "email_sender": sender}

    with pytest.raises(PermanentJobError):
        await password_reset_email(ctx, recipient="user@example.com", reset_url="https://app/reset?token=x")

    assert "secret-reset-token" not in caplog.text
    outcome = next(record for record in caplog.records if record.message == "background_job_outcome")
    assert outcome.outcome == "terminal_failure"


@pytest.mark.asyncio
async def test_report_generation_contract_dispatches_to_handler():
    handler = AsyncMock()
    ctx = {"job_id": "report-job", "job_try": 1, "settings": settings(), "report_generator": handler}

    await generate_report(
        ctx,
        report_type="inventory",
        report_id="report-1",
        requested_by="user-1",
    )

    handler.assert_awaited_once_with(
        report_type="inventory",
        report_id="report-1",
        requested_by="user-1",
    )


@pytest.mark.asyncio
async def test_missing_report_handler_is_terminal():
    with pytest.raises(PermanentJobError):
        await generate_report(
            {"job_id": "report-job", "job_try": 1, "settings": settings()},
            report_type="inventory",
            report_id="report-1",
            requested_by="user-1",
        )


@pytest.mark.asyncio
async def test_console_sender_never_logs_reset_url(caplog):
    caplog.set_level("INFO")
    await ConsoleEmailSender().send_password_reset(
        recipient="user@example.com",
        reset_url="https://app/reset?token=secret-reset-token",
    )
    assert "secret-reset-token" not in caplog.text
    assert any(record.message == "password_reset_email_delivered" for record in caplog.records)
