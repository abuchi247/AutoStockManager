"""ARQ background job contracts, worker functions, and safe job telemetry.

Jobs deliberately receive explicit, small payloads.  Worker logs contain only
opaque job metadata and outcome classifications; credentials and reset URLs are
never included in log fields or exception messages.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import time
import uuid
from email.message import EmailMessage
from typing import Any, Awaitable, Callable, Protocol, TypedDict

from arq import Retry, create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job
from arq.worker import Worker

from app.config import Settings, get_settings
from app.telemetry import get_telemetry, get_trace_context, trace_id_var
from app.middleware.request_id import request_id_var

logger = logging.getLogger(__name__)

PASSWORD_RESET_EMAIL_JOB = "password_reset_email"
REPORT_GENERATION_JOB = "generate_report"
SUPPORTED_JOB_NAMES = frozenset({PASSWORD_RESET_EMAIL_JOB, REPORT_GENERATION_JOB})


class PasswordResetEmailPayload(TypedDict):
    """Payload contract for password-reset delivery."""

    recipient: str
    reset_url: str


class ReportGenerationPayload(TypedDict):
    """Future report job contract; report generation is intentionally pluggable."""

    report_type: str
    report_id: str
    requested_by: str


class EmailSender(Protocol):
    async def send_password_reset(self, *, recipient: str, reset_url: str) -> None:
        """Deliver a password-reset link without returning it to the API."""


class TransientJobError(Exception):
    """A failure that ARQ should retry."""


class PermanentJobError(Exception):
    """A non-retryable job failure."""


def _job_context(ctx: dict[str, Any]) -> tuple[str, int, Settings]:
    job_id = str(ctx.get("job_id") or "unknown")
    try:
        attempt = max(1, int(ctx.get("job_try", 1)))
    except (TypeError, ValueError):
        attempt = 1
    settings = ctx.get("settings") or get_settings()
    return job_id, attempt, settings


def _log_outcome(job_id: str, job_name: str, attempt: int, outcome: str) -> None:
    # Keep this event safe for JSON formatters: no exception text or payload is
    # included because payloads may contain reset URLs or recipient details.
    # Include trace context so job outcomes can be correlated with the
    # originating request in distributed tracing pipelines.
    trace_ctx = get_trace_context()
    logger.info(
        "background_job_outcome",
        extra={
            "job_id": job_id,
            "job_name": job_name,
            "attempt": attempt,
            "outcome": outcome,
            **trace_ctx,
        },
    )


def retry_delay(attempt: int, settings: Settings) -> float:
    """Return bounded exponential backoff for the next transient attempt."""
    exponent = max(0, attempt - 1)
    return min(
        settings.job_max_backoff_seconds,
        settings.job_base_backoff_seconds * (2**exponent),
    )


async def _run_job(
    ctx: dict[str, Any],
    job_name: str,
    operation: Callable[[], Awaitable[None]],
) -> None:
    job_id, attempt, settings = _job_context(ctx)

    # Restore trace context propagated from the enqueuing request so that job
    # logs, metrics, and error tracking correlate with the originating API call.
    propagated_request_id = ctx.get("_propagated_request_id")
    propagated_trace_id = ctx.get("_propagated_trace_id")
    request_id_token = None
    trace_id_token = None
    if propagated_request_id:
        request_id_token = request_id_var.set(propagated_request_id)
    if propagated_trace_id:
        trace_id_token = trace_id_var.set(propagated_trace_id)

    telemetry = get_telemetry()
    start_time = time.perf_counter()
    try:
        await operation()
    except TransientJobError:
        duration_ms = (time.perf_counter() - start_time) * 1000
        if attempt >= settings.job_max_tries:
            _log_outcome(job_id, job_name, attempt, "terminal_failure")
            telemetry.record_job_duration(
                job_name=job_name, duration_ms=duration_ms, success=False
            )
            raise
        _log_outcome(job_id, job_name, attempt, "retry")
        telemetry.record_job_duration(
            job_name=job_name, duration_ms=duration_ms, success=False
        )
        raise Retry(defer=retry_delay(attempt, settings))
    except PermanentJobError:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _log_outcome(job_id, job_name, attempt, "terminal_failure")
        telemetry.record_job_duration(
            job_name=job_name, duration_ms=duration_ms, success=False
        )
        raise
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000
        # Unknown failures are terminal by default.  This prevents retries from
        # duplicating an operation whose transient nature was not established.
        _log_outcome(job_id, job_name, attempt, "terminal_failure")
        telemetry.record_job_duration(
            job_name=job_name, duration_ms=duration_ms, success=False
        )
        raise PermanentJobError("background job failed")
    else:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _log_outcome(job_id, job_name, attempt, "success")
        telemetry.record_job_duration(
            job_name=job_name, duration_ms=duration_ms, success=True
        )
    finally:
        if request_id_token is not None:
            request_id_var.reset(request_id_token)
        if trace_id_token is not None:
            trace_id_var.reset(trace_id_token)


class SMTPEmailSender:
    """SMTP sender whose network operation runs outside the event loop."""

    def __init__(self, settings: Settings) -> None:
        if not settings.smtp_host or not settings.smtp_from_email:
            raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL are required for email jobs")
        self.settings = settings

    def _send(self, recipient: str, reset_url: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from_email
        message["To"] = recipient
        message["Subject"] = "Password reset"
        message.set_content(
            "Use the following link to reset your password:\n\n"
            f"{reset_url}\n"
        )
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password or "")
            smtp.send_message(message)

    async def send_password_reset(self, *, recipient: str, reset_url: str) -> None:
        try:
            await asyncio.to_thread(self._send, recipient, reset_url)
        except (OSError, TimeoutError, smtplib.SMTPException) as exc:
            # Do not retain or expose the exception text; SMTP errors can echo
            # message contents or connection credentials.
            raise TransientJobError from exc


class ConsoleEmailSender:
    """Development sender that redacts the token before writing a log event."""

    async def send_password_reset(self, *, recipient: str, reset_url: str) -> None:
        # Deliberately log only that delivery was requested.  The reset URL and
        # token are never emitted, even in development.
        logger.info(
            "password_reset_email_delivered",
            extra={"recipient": recipient, "delivery": "console"},
        )


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.smtp_host:
        return SMTPEmailSender(settings)
    if settings.environment == "development":
        return ConsoleEmailSender()
    raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL are required outside development")


async def password_reset_email(
    ctx: dict[str, Any], *, recipient: str, reset_url: str,
    _propagated_request_id: str | None = None,
    _propagated_trace_id: str | None = None,
) -> None:
    # Store propagated trace context in the job context for _run_job to restore.
    if _propagated_request_id:
        ctx["_propagated_request_id"] = _propagated_request_id
    if _propagated_trace_id:
        ctx["_propagated_trace_id"] = _propagated_trace_id
    sender: EmailSender = ctx.get("email_sender") or build_email_sender(_job_context(ctx)[2])
    await _run_job(
        ctx,
        PASSWORD_RESET_EMAIL_JOB,
        lambda: sender.send_password_reset(recipient=recipient, reset_url=reset_url),
    )


async def generate_report(
    ctx: dict[str, Any], *, report_type: str, report_id: str, requested_by: str,
    _propagated_request_id: str | None = None,
    _propagated_trace_id: str | None = None,
) -> None:
    """Dispatch the future report contract to an injected report handler."""
    # Store propagated trace context in the job context for _run_job to restore.
    if _propagated_request_id:
        ctx["_propagated_request_id"] = _propagated_request_id
    if _propagated_trace_id:
        ctx["_propagated_trace_id"] = _propagated_trace_id
    handler = ctx.get("report_generator")
    if handler is None:
        raise PermanentJobError("report generation is not configured")
    await _run_job(
        ctx,
        REPORT_GENERATION_JOB,
        lambda: handler(
            report_type=report_type,
            report_id=report_id,
            requested_by=requested_by,
        ),
    )


async def worker_startup(ctx: dict[str, Any]) -> None:
    ctx["settings"] = get_settings()
    ctx["email_sender"] = build_email_sender(ctx["settings"])


async def worker_shutdown(ctx: dict[str, Any]) -> None:
    ctx.pop("email_sender", None)


class WorkerSettings:
    """ARQ CLI configuration: ``arq app.services.background_jobs.WorkerSettings``."""

    _settings = get_settings()
    functions = [password_reset_email, generate_report]
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    queue_name = _settings.job_queue_name
    max_jobs = _settings.job_max_concurrency
    job_timeout = _settings.job_timeout_seconds
    max_tries = _settings.job_max_tries
    retry_jobs = True
    on_startup = worker_startup
    on_shutdown = worker_shutdown


def create_worker(settings: Settings | None = None) -> Worker:
    settings = settings or get_settings()
    return Worker(
        functions=[password_reset_email, generate_report],
        redis_settings=RedisSettings.from_dsn(settings.redis_url),
        queue_name=settings.job_queue_name,
        max_jobs=settings.job_max_concurrency,
        job_timeout=settings.job_timeout_seconds,
        max_tries=settings.job_max_tries,
        retry_jobs=True,
        on_startup=worker_startup,
        on_shutdown=worker_shutdown,
    )


_arq_pool: ArqRedis | None = None
_arq_pool_lock = asyncio.Lock()


async def get_arq_pool(settings: Settings | None = None) -> ArqRedis:
    global _arq_pool
    if _arq_pool is None:
        async with _arq_pool_lock:
            if _arq_pool is None:
                settings = settings or get_settings()
                _arq_pool = await create_pool(
                    RedisSettings.from_dsn(settings.redis_url),
                    default_queue_name=settings.job_queue_name,
                )
    return _arq_pool


async def close_arq_pool() -> None:
    global _arq_pool
    if _arq_pool is not None:
        _arq_pool.close()
        _arq_pool = None


async def enqueue_job(
    job_name: str,
    payload: dict[str, Any],
    settings: Settings | None = None,
) -> str:
    """Enqueue a validated job and return its opaque ARQ job ID.

    Propagates the current request/trace IDs into the job so worker logs and
    metrics can be correlated with the originating API request.
    """
    if job_name not in SUPPORTED_JOB_NAMES:
        raise ValueError("unsupported background job")
    job_id = str(uuid.uuid4())
    pool = await get_arq_pool(settings)

    # Propagate trace context from the request that enqueued this job.
    trace_ctx = get_trace_context()
    payload = {
        **payload,
        "_propagated_request_id": trace_ctx.get("request_id"),
        "_propagated_trace_id": trace_ctx.get("trace_id"),
    }

    await pool.enqueue_job(job_name, _job_id=job_id, **payload)
    return job_id


async def get_job_status(job_id: str, settings: Settings | None = None) -> dict[str, str]:
    """Return safe operational status without exposing job arguments/results."""
    settings = settings or get_settings()
    pool = await get_arq_pool(settings)
    status = await Job(job_id, pool, _queue_name=settings.job_queue_name).status()
    return {"job_id": job_id, "status": status.value}
