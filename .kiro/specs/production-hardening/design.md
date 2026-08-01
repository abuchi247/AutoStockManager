# Design Document: Production Hardening

## Overview

This design hardens the existing AutoStockManager application without changing its ERP domain model or introducing subscription billing. The work is organized into three layers:

1. **Security boundary**: validate production secrets, deliver password-reset credentials safely, move browser refresh tokens to HTTP-only cookies, and tighten request handling.
2. **Operational boundary**: add structured request-correlated logs, error tracking, dependency-aware health checks, deterministic migrations, background jobs, and CI enforcement.
3. **Frontend boundary**: add resilient route fallbacks, centralized server-state management, schema-driven forms, automated tests, and a dependency upgrade process.

The implementation should preserve the existing FastAPI service layer, Redis session registry, PostgreSQL database, Next.js App Router, and Axios API abstraction. New infrastructure is introduced behind small interfaces so it can be replaced or disabled in development.

## Goals and Non-Goals

### Goals

- Prevent known insecure production configurations from starting.
- Ensure password-reset tokens are never returned to normal API clients.
- Reduce browser token theft risk by moving refresh tokens out of JavaScript-readable storage.
- Make failures diagnosable through request IDs, structured logs, error tracking, and health checks.
- Make database schema state controlled exclusively by Alembic.
- Move slow/retriable work out of request handlers.
- Make frontend data fetching, validation, and failure handling consistent.
- Make all required checks reproducible in CI.

### Non-Goals

- Subscription plans, billing, Stripe, or tenant isolation.
- A full rewrite of the authentication system.
- A mandatory immediate upgrade to Next.js 15 or React 19.
- Changing existing ERP permissions, ledger behavior, inventory calculations, or API resource semantics.
- Replacing Redis or PostgreSQL.

## Existing Constraints and Decisions

### Authentication transition

The current browser client stores both JWTs in `localStorage`. The target design stores only the short-lived access token in memory and stores the refresh token in an HTTP-only cookie. The backend will support both cookie-based browser refresh and the existing JSON body for explicitly identified non-browser clients during a compatibility window.

The cookie is configured with:

- `HttpOnly=true`
- `Secure=true` in staging/production
- `SameSite=Strict` when frontend and API share the same site; configurable for deployments that require cross-site hosting
- A narrow `Path`, preferably `/api/v1/auth`, so the browser does not send the refresh credential to unrelated endpoints
- A configurable name that does not expose token contents

Because cookie authentication introduces CSRF considerations, state-changing cookie-authenticated endpoints will validate the expected origin and/or use a CSRF defense. The access-token `Authorization` flow remains available for non-browser clients.

### Error tracking provider

Use an adapter around a provider such as Sentry rather than coupling business services directly to an SDK. The adapter is a no-op when disabled. The DSN, environment, release, sample rate, and enabled flag are configuration values. Sensitive headers, cookies, authorization values, request bodies, password fields, reset tokens, and database credentials must be scrubbed before transmission.

### Background jobs

Use the existing Redis deployment with ARQ as the first implementation because it is asyncio-native and fits the FastAPI/async SQLAlchemy stack. Jobs have explicit names, bounded retry counts, exponential backoff, and structured success/failure logs. The job interface should allow a later worker replacement without changing request handlers.

### Query and form libraries

Use TanStack Query for server state and React Hook Form with Zod for form state and validation. These choices complement the existing Axios client and TypeScript setup. The API client remains the single transport layer; Query hooks call typed API functions rather than making raw Axios calls from page components.

## Architecture

```text
Browser
  |
  | access token in memory + refresh cookie
  v
Next.js UI
  |-- Error boundaries / error pages
  |-- TanStack Query hooks
  |-- React Hook Form + Zod schemas
  |-- API client with centralized auth/error handling
  v
FastAPI application
  |-- Request ID middleware
  |-- Request size / CORS / security middleware
  |-- Exception and error-tracker integration
  |-- Auth router (cookie-aware refresh/logout)
  |-- Domain routers and services
  |-- Background job enqueue adapter
  |-- Health endpoints
  |-- Alembic migration runner at startup
  v
PostgreSQL        Redis                 ARQ worker
  |                 |                     |
  |                 | sessions/limits    | email/report jobs
  +-----------------+---------------------+
```

## Backend Components

### Configuration and startup validation

Extend `app/config.py` with production-safe settings:

- `log_level`
- `max_request_body_bytes` defaulting to 5 MB
- `health_check_timeout_seconds` defaulting to 2 seconds
- `refresh_cookie_name`, `refresh_cookie_secure`, `refresh_cookie_samesite`, and `refresh_cookie_path`
- SMTP settings and frontend reset URL
- error-tracker enablement, DSN, environment, release, and sample rate
- job queue settings
- optional `run_migrations_on_startup` flag, enabled in deployment configuration

Add a settings validation method invoked during application creation/lifespan. Production validation must reject placeholder/short JWT secrets and placeholder database passwords. The validator must never include secret values in exception text or logs.

### Request hardening middleware

Add middleware components with deterministic ordering:

1. Request ID middleware: accept a valid incoming `X-Request-ID` or generate a UUID; attach it to request state, response headers, and logging context.
2. Request-size middleware: inspect `Content-Length` where available and enforce a streaming/read limit for chunked requests; return 413 with a stable error shape.
3. Existing security headers middleware.
4. CORS middleware with explicit methods and headers.

Authentication routes receive stricter limits than general routes. The limiter must use the existing Redis-backed mechanism and must not trust an unvalidated JWT merely to grant a privileged limit.

### Structured logging and exception handling

Create a logging setup module with:

- JSON formatter for non-development environments and readable formatter for local development.
- Standard fields: timestamp, level, logger, message, request ID, environment, service, and optional route/method.
- Context propagation using a request-scoped context variable.
- Redaction for authorization headers, cookies, passwords, reset tokens, JWTs, database URLs, and common secret keys.

Add a global exception handler that logs the exception with request context, reports it through the error-tracker adapter if enabled, and returns a generic response in staging/production. Validation and expected HTTP errors retain their existing status codes and safe details.

### Password reset and notification service

Introduce interfaces similar to:

```python
class EmailSender(Protocol):
    async def send_password_reset(self, *, recipient: str, reset_url: str) -> None: ...

class JobQueue(Protocol):
    async def enqueue(self, job_name: str, payload: dict[str, Any]) -> str: ...
```

Implement:

- SMTP sender for staging/production.
- Console/log sender for development that emits a redacted, clearly non-production reset URL.
- ARQ job function that invokes the sender and retries transient errors.
- Generic password-reset response regardless of whether the email exists.
- One-time reset token persistence or a Redis used-token marker keyed by token JTI with TTL equal to token expiry. The marker must be checked atomically before accepting the reset.

The response schema must no longer expose `reset_token`. The reset link is constructed from a configured frontend base URL and the token is only placed in the outbound email job payload. Job logs must not print the token.

### Cookie-based refresh flow

Update auth service/router contracts as follows:

- Login returns the access token in the JSON response and sets the refresh token cookie. A compatibility flag may temporarily include the body refresh token only for non-browser clients.
- Refresh reads a refresh token from the cookie first, then accepts a body token for non-browser clients. It rotates the refresh session in Redis and sets a replacement cookie.
- Logout reads the cookie/body token, removes the session, and expires the cookie.
- Refresh and logout responses must not expose cookie credentials.
- Password reset must revoke all active sessions after a successful password change.

The frontend API client must use `withCredentials: true`, retain access tokens in a module-level memory store, and initialize the session by attempting one refresh call after a page load. Concurrent 401s continue to use the existing single-refresh queue.

### Health checks

Keep `/health` as a liveness/readiness-style endpoint but make dependency status explicit. Run database `SELECT 1` and Redis `PING` concurrently with `asyncio.wait_for`. Return:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "commit": "...",
  "dependencies": {
    "database": "up",
    "redis": "up"
  }
}
```

Return HTTP 503 and `status: unhealthy` if either critical dependency fails. Do not include connection strings, exception stack traces, or credentials in the response. A separate lightweight liveness endpoint may be retained if deployment needs a check that does not depend on external services.

### Alembic-only schema management

Refactor startup so it imports models and verifies configuration but does not call `Base.metadata.create_all` or execute inline schema patches. Add an Alembic revision for `sales.amount_paid` if it is not already represented by the migration history. Run `alembic upgrade head` as a deployment step or controlled startup operation. If startup migration execution is enabled, migration failure must abort startup.

The migration runner must use the same database URL configuration as the application, emit migration start/success/failure events without secrets, and avoid concurrent migration races in multi-instance deployments through deployment serialization or a database advisory lock.

### Production documentation access

Keep public `/docs` and `/redoc` disabled in production. Add a separate protected mechanism for internal documentation, preferably a route that requires an Admin dependency and is additionally restricted by an internal network or deployment ingress. Do not expose the OpenAPI schema publicly by accident.

### CI and operational files

Add a GitHub Actions workflow with separate backend and frontend jobs plus a Docker build job. Use lockfiles and cached dependencies. The workflow should run:

- Backend formatting/linting/type checks where configured, pytest including property tests, and Docker build.
- Frontend lint, TypeScript `--noEmit`, unit/component tests, and production build.
- Playwright tests in a job with required services or a controlled test environment.

Document required checks, local commands, environment variables, migration execution, backup expectations, and error-tracker setup in project documentation or an operations runbook.

## Frontend Components

### Error resilience

Add App Router `error.tsx` and `not-found.tsx` files at the root and relevant route-group boundaries. The fallback must:

- Explain that the page failed without exposing internal exception details.
- Provide retry/reset and navigation actions.
- Report the error once with route context through the error-tracker adapter.
- Respect the existing visual language and accessibility requirements.

### Query client

Create a browser-side QueryClient provider at the application root with conservative defaults: no aggressive refetch loops, bounded stale times, retry only for transient errors, and a global mutation/error policy. Convert feature areas incrementally to typed query/mutation hooks. Query keys must be centralized and mutations must invalidate affected resources.

The Axios client remains responsible for transport, refresh coordination, and normalized API errors. Query hooks consume that client and do not duplicate redirect/toast logic.

### Forms and API validation errors

Create reusable Zod schemas and React Hook Form adapters for the main create/update flows. Define a normalized frontend error type that can represent FastAPI validation errors (`loc`, `msg`, `type`) and map field paths to form controls. Keep backend validation authoritative; client validation is an early feedback layer and must not weaken server checks.

### Frontend tests

Configure:

- Vitest and React Testing Library for API client, token store, error boundary, and representative forms/components.
- MSW or an equivalent request mock layer for deterministic API behavior.
- Playwright for login and one core ERP flow, with secrets and test data supplied only through CI environment variables.

Tests must cover token refresh queueing, logout behavior, cookie-based refresh requests, query invalidation, field validation, backend validation mapping, error fallback/reset, and the primary e2e flow.

### Dependency currency

Record supported Next.js/React major versions and an upgrade checklist. Do not perform a major upgrade as an implicit part of this hardening work. Renovate/Dependabot or a scheduled dependency audit may be added later, but all security updates must be reviewed and tested before merging.

## Data Flow

### Password reset

```text
Client -> POST /auth/reset-password
       -> validate request and return generic 200 response
       -> lookup user without revealing existence
       -> create one-time reset token
       -> enqueue password-reset email job
       -> worker sends reset link or retries transient failure
Client -> POST /auth/reset-password/confirm
       -> validate token type, expiry, and unused marker atomically
       -> update password and revoke all sessions
       -> mark token used
```

### Browser authentication

```text
Login -> access token JSON + refresh cookie
API request -> Authorization: Bearer <in-memory access token>
401 -> one queued cookie-authenticated refresh request
Refresh -> rotate Redis session + replacement refresh cookie + new access token
Logout -> revoke Redis JTI + expire refresh cookie + clear in-memory access token
```

### Request observability

```text
Request -> request ID middleware -> context variable
        -> route/service logs include request ID
        -> exception handler captures safe context
        -> response includes X-Request-ID
```

## Error Handling

- Configuration errors: fail closed during production startup with an actionable message that identifies the setting name, never its value.
- Authentication failures: preserve 401/403/423 semantics and generic credential messages.
- Oversized requests: return 413 with a stable error code.
- Dependency failures: health endpoint returns 503; normal request failures use generic 5xx responses and structured logs.
- Email/job failures: retry transient failures, log job ID and safe error classification, and expose a safe operational status.
- Frontend request failures: normalize once in the API client; Query and forms consume normalized errors.
- Frontend rendering failures: route-level fallback with reset action and error-tracker report.

## Testing Strategy

### Backend

- Unit tests for production settings validation, redaction, request IDs, request-size limits, CORS configuration, cookie attributes, reset-token one-time use, email sender selection, job retry behavior, and health-check status/timeout behavior.
- Integration tests for login/refresh/logout browser flow, password reset flow, Alembic upgrade from the current schema, and protected documentation access.
- Regression tests for existing auth, session rotation, RBAC, and API routes.

### Frontend

- Unit tests for memory-only token storage and absence of localStorage token writes.
- API client tests for `withCredentials`, refresh queueing, cookie-based refresh, and logout cleanup.
- Component tests for error boundaries, loading/error/empty states, forms, and validation mapping.
- E2E tests for login/session restoration and creating a sale.

### Operational validation

- Build backend and frontend containers.
- Run the complete test suite in CI.
- Start a production-like compose environment with non-placeholder secrets.
- Confirm health status changes to unhealthy when PostgreSQL or Redis is unavailable.
- Confirm production startup fails on weak secrets and migration failure.

## Rollout Plan

1. Add configuration validation, structured logging, request IDs, health checks, and tests. These are low-risk and provide visibility for the remaining changes.
2. Add Alembic migration discipline and deployment migration execution. Validate against a database snapshot before removing startup DDL.
3. Add email abstraction, background worker, one-time reset tokens, and generic reset responses.
4. Deploy cookie-based authentication behind a compatibility flag. Update the frontend, verify refresh/logout across browser sessions, then remove browser `localStorage` token support.
5. Add frontend QueryClient, schemas, error boundaries, tests, and CI gates incrementally by route group.
6. Enable error tracking and required CI checks in staging first, then production.

Each rollout stage should have a rollback plan. In particular, retain the old non-browser refresh-body flow until all supported browser clients have migrated, and do not remove `create_all` until the existing production schema has been verified against Alembic head.

## Security Considerations

- Never log secrets or send them to error tracking.
- Validate forwarded client IP headers only when requests come through trusted proxies; otherwise use the socket address.
- Use secure cookies and HTTPS in staging/production.
- Use CSRF protection for cookie-authenticated state-changing requests.
- Avoid returning reset tokens in any normal API response.
- Revoke all sessions after password reset and rotate refresh tokens on every refresh.
- Restrict production API documentation to authenticated/internal users.
- Keep dependency versions pinned by lockfiles and scan them regularly.
- Ensure CI secrets are injected through the CI secret store and never committed.


## Performance, Reliability, and Recovery Design

### Backend performance controls

Treat performance as a correctness requirement, not a post-release optimization. Every collection and report endpoint must define its pagination contract, maximum result size, stable sort order, and filter behavior. Prefer cursor pagination for high-volume or frequently changing datasets; offset pagination is acceptable for small administrative lists with an explicit maximum offset.

Review SQLAlchemy statements for N+1 behavior using explicit `selectinload`/`joinedload` only where appropriate, projection queries for list views, and query-plan inspection with representative production-like data. Add indexes based on measured query plans and existing filter/join patterns rather than indexing every column. Avoid loading full ORM graphs when a response needs only a few fields.

Use bounded PostgreSQL pool sizes, acquisition timeouts, statement timeouts, and Redis command timeouts. Set worker concurrency based on database capacity rather than CPU count alone. Add backpressure to background queues and reject or defer work when queue depth or resource saturation exceeds configured limits. Graceful shutdown must stop accepting new work, allow a bounded drain period, and safely requeue or mark interrupted jobs.

Use cache-aside only for explicitly listed, non-sensitive read models. Namespaces must include the resource and version; TTL and invalidation must be documented. Redis is an optimization and coordination dependency, not the sole source of truth for financial or inventory data.

For retryable non-idempotent actions, require an idempotency key scoped to the authenticated actor and operation. Persist the key/result long enough to cover client retries, enforce request-body consistency for a reused key, and return the original result rather than executing the side effect twice. Background jobs must have a stable deduplication key and be safe to retry.

### Metrics, traces, and performance budgets

Add a metrics/tracing adapter alongside logs and error tracking. At minimum record request totals, status classes, route latency histograms, database pool wait time, slow-query counts, Redis failures, queue depth, job duration/failures, and dependency health. Propagate the request ID and, where tracing is enabled, a trace ID across API calls and background jobs. Scrub the same sensitive fields as logs before export.

Define initial budgets in configuration and the operations runbook. Suggested starting points are p95 under 500 ms for ordinary authenticated CRUD endpoints, p95 under 2 seconds for explicitly identified reports, and API error rate under 1% excluding expected 4xx responses. These are starting thresholds to be measured and adjusted using production evidence, not guarantees for every endpoint. Frontend budgets should be set from a production build and representative network/device profile.

### Backup and recovery

Use managed PostgreSQL point-in-time recovery where available, supplemented by encrypted logical backups and an off-host copy. Do not treat Redis session data as a database backup requirement, but document that active sessions may be invalidated during Redis loss or restoration. Generated invoices/reports and any uploaded assets require their own durable storage and backup policy.

Use separate least-privileged application and migration database identities. Encrypt backups, restrict restore access, and test restores into an isolated environment. Record restore duration and data-integrity checks against append-only ledgers, sales, purchases, invoices, users, and audit trails. Define RPO/RTO before production launch and rehearse the runbook.

### Release and container hardening

CI must scan Python/Node dependencies and container images, fail or require an expiring exception for critical/high findings according to the security policy, and attach scan results to the commit-tagged artifact. Production images must exclude source mounts, development tooling, debug settings, and default credentials. Run the application as a non-root user, expose only required ports, and restrict writable directories.

### Frontend performance and accessibility

Use Next.js route boundaries and dynamic imports to keep initial bundles small. Keep reports, PDF viewers, charting, and other heavy libraries out of the initial dashboard bundle unless required for first render. Use TanStack Query to parallelize independent requests, prefetch predictable navigation targets, and avoid refetch storms. Use server-side pagination and debounced filters for inventory, sales, customer, supplier, and report lists; virtualize large tables while preserving keyboard and screen-reader semantics.

Measure production builds with Lighthouse or an equivalent tool and a repeatable device/network profile. Track JavaScript bundle sizes, route load time, LCP, INP, CLS, API wait time, and table interaction latency. Add automated accessibility checks with keyboard-focused component tests and an axe-compatible scanner for representative routes. Loading, validation, and error states must announce important changes accessibly and preserve focus.

### Graceful degradation matrix

Document expected behavior when dependencies fail:

- PostgreSQL unavailable: writes fail safely, reads return a generic dependency error, and health readiness is unhealthy.
- Redis unavailable: do not silently bypass refresh-token revocation or rate limiting; use an explicit fail-closed or documented degraded mode per endpoint.
- Email provider unavailable: reset requests remain generic, jobs retry, and operators receive an alert; never return the token.
- Error tracker/metrics unavailable: requests continue, while local structured logs remain sufficient for diagnosis.
- Background worker unavailable: enqueue failures are visible and user-facing operations do not claim that an email/report was completed.
