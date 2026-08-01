# Requirements Document

## Introduction

The Auto Spare Parts ERP System (AutoStockManager) has a solid functional foundation but was built without several safeguards required to run safely in production and to support paying customers reliably. This spec addresses security hardening, production infrastructure, frontend robustness, performance, recovery, and release quality.

This effort does not introduce new business features (e.g. subscriptions/billing are covered separately). It closes gaps in the existing system so that it is safe to operate, observable when things go wrong, resilient on both the backend and frontend, and able to scale predictably. Where a fix conflicts with the current single-tenant, token-in-localStorage architecture, this document favors the minimal change that removes the risk without a large rewrite, and calls out follow-on work explicitly.

Technology stack: Python FastAPI backend with SQLAlchemy 2.0 (async) and PostgreSQL, Redis for sessions/rate limiting, Next.js 14 frontend with TypeScript and Tailwind CSS, Docker Compose deployment.

## Glossary

- **Security_Manager**: The existing module responsible for JWT authentication, RBAC enforcement, rate limiting, and session management (extended by this spec)
- **Secrets_Manager**: The mechanism by which sensitive configuration values (JWT secret, database credentials) are generated, validated, and supplied to the application
- **Token_Store**: The client-side mechanism used to persist access and refresh tokens between page loads
- **Notification_Service**: The backend component responsible for sending outbound email (e.g. password reset links) instead of returning secrets directly in API responses
- **Health_Check**: An HTTP endpoint that reports the availability of the application and its critical dependencies (database, Redis)
- **Structured_Logger**: A logging configuration that emits machine-parseable (JSON) log records with consistent fields (timestamp, level, request_id, logger name, message)
- **Error_Tracker**: A third-party service (e.g. Sentry) integrated into both backend and frontend to capture and alert on unhandled exceptions
- **Migration_Runner**: The Alembic-based process that applies versioned schema changes; replaces the ad hoc `create_all` and inline SQL patches currently run at startup
- **CI_Pipeline**: An automated workflow that lints, type-checks, tests, scans, and builds the application on every push/pull request
- **Error_Boundary**: A React component that catches rendering errors in its child component tree and displays a fallback UI instead of crashing the whole page
- **Query_Client**: A frontend data-fetching/caching layer (e.g. TanStack Query) used to manage server state, loading, and error states consistently across the app
- **Form_Validator**: A frontend validation layer (e.g. react-hook-form + zod) used to validate user input before submission and surface field-level errors
- **Frontend_Test_Runner**: The test framework (e.g. Vitest/Jest + React Testing Library, and Playwright for e2e) used to verify frontend behavior

## Requirements

### Requirement 1: Secret and Credential Management

**User Story:** As an operator, I want the application to refuse to start with weak or default secrets, so that a misconfigured production deployment cannot silently run with an insecure JWT signing key.

#### Acceptance Criteria

1. WHEN the application starts with `environment` set to `production`, THE Secrets_Manager SHALL raise a startup error if `jwt_secret_key` equals its default placeholder value or is shorter than 32 characters
2. WHEN the application starts with `environment` set to `production`, THE Secrets_Manager SHALL raise a startup error if `POSTGRES_PASSWORD` equals a known placeholder value (e.g. `changeme`)
3. THE Secrets_Manager SHALL document a command to generate a cryptographically random secret (minimum 32 bytes) in `.env.example`
4. THE ERP_System SHALL NOT log the value of any secret (JWT secret, database URL credentials, tokens) at any log level

### Requirement 2: Credential Delivery for Password Reset

**User Story:** As a user who forgot my password, I want to receive a reset link by email, so that another person with API access cannot read or reuse my reset token.

#### Acceptance Criteria

1. WHEN a password reset is requested for an email that exists, THE Notification_Service SHALL send the reset link to that email address instead of returning the raw token in the API response
2. WHEN a password reset is requested for an email that does not exist, THE ERP_System SHALL return the same generic success response as for an existing email, to prevent account enumeration
3. THE ERP_System SHALL support a pluggable email backend (SMTP by default) configured via environment variables, with a development mode that logs the email content instead of sending it
4. WHEN a password reset token has been used successfully, THE ERP_System SHALL invalidate it so it cannot be replayed

### Requirement 3: Token Storage and Exposure

**User Story:** As a user, I want my session tokens to be reasonably protected from theft via cross-site scripting, so that a compromised third-party script cannot silently exfiltrate my login session.

#### Acceptance Criteria

1. THE ERP_System SHALL issue the refresh token as an HTTP-only, `Secure`, `SameSite=Strict` cookie rather than a value readable by client-side JavaScript
2. THE frontend Token_Store SHALL retain the access token only in memory (not `localStorage`) for the duration of the session
3. WHEN the access token expires, THE frontend SHALL transparently obtain a new access token using the HTTP-only refresh cookie without requiring the user to re-authenticate
4. WHEN a user logs out, THE ERP_System SHALL clear the refresh cookie and invalidate the corresponding session entry
5. THE backend auth endpoints SHALL accept the refresh token from the HTTP-only cookie for `/api/v1/auth/refresh` and `/api/v1/auth/logout`, and SHALL continue to support the existing request-body flow only for non-browser API clients

### Requirement 4: CORS and Request Hardening

**User Story:** As a security-conscious operator, I want the API to only accept the HTTP methods and headers it actually needs, so that the attack surface for cross-origin and payload-based attacks is minimized.

#### Acceptance Criteria

1. THE ERP_System SHALL restrict CORS `allow_methods` to the specific methods used by the API (GET, POST, PUT, PATCH, DELETE, OPTIONS) instead of a wildcard
2. THE ERP_System SHALL restrict CORS `allow_headers` to the specific headers required (Authorization, Content-Type) instead of a wildcard
3. THE ERP_System SHALL reject incoming request bodies larger than a configurable maximum size (default 5 MB) with an HTTP 413 response
4. THE ERP_System SHALL apply the existing rate limiter to authentication endpoints at a stricter threshold than general API endpoints, to slow down credential-stuffing attempts

### Requirement 5: Structured Logging

**User Story:** As an operator, I want consistent, structured logs across the backend, so that I can search, filter, and correlate log events when investigating an incident.

#### Acceptance Criteria

1. THE Structured_Logger SHALL emit JSON-formatted log records containing timestamp, log level, logger name, message, and request_id
2. WHEN an incoming HTTP request is received, THE ERP_System SHALL generate or propagate a request_id (from an `X-Request-ID` header if present) and include it in all log records emitted while handling that request
3. THE ERP_System SHALL configure log verbosity per environment (DEBUG in development, INFO in staging/production) via existing settings
4. THE Structured_Logger SHALL NOT emit request or response bodies containing password, token, or secret fields; such fields SHALL be redacted before logging

### Requirement 6: Error Tracking

**User Story:** As a developer, I want unhandled exceptions in both backend and frontend to be automatically captured and reported, so that I learn about production errors without depending on user reports.

#### Acceptance Criteria

1. WHEN an unhandled exception occurs in the backend request lifecycle, THE Error_Tracker SHALL capture the exception with request context (route, method, request_id, user id if authenticated) excluding secret fields
2. WHEN an unhandled exception occurs in the frontend, THE Error_Tracker SHALL capture the exception with the current route and a redacted breadcrumb trail
3. THE Error_Tracker integration SHALL be disabled by default in local development and enabled via an environment variable and DSN in staging/production
4. THE ERP_System SHALL continue to return a generic error response to the client when an unhandled exception occurs, without leaking stack traces or internal details in staging/production

### Requirement 7: Dependency Health Checks

**User Story:** As an operator running this behind a load balancer or orchestrator, I want the health check to reflect the real availability of dependencies, so that traffic is not routed to an instance that cannot reach its database or cache.

#### Acceptance Criteria

1. WHEN `/health` is requested, THE Health_Check SHALL verify connectivity to PostgreSQL with a lightweight query and report `"database": "up"` or `"database": "down"`
2. WHEN `/health` is requested, THE Health_Check SHALL verify connectivity to Redis with a PING and report `"redis": "up"` or `"redis": "down"`
3. IF any critical dependency is down, THEN THE Health_Check SHALL respond with HTTP 503 and an overall `"status": "unhealthy"`
4. THE Health_Check SHALL respond within a bounded timeout (default 2 seconds per dependency) so that a hung dependency does not hang the health check itself

### Requirement 8: Database Migration Discipline

**User Story:** As an operator, I want schema changes to be applied through a single, reviewable migration path, so that production schema state is predictable and reversible.

#### Acceptance Criteria

1. THE Migration_Runner SHALL apply pending Alembic migrations on application startup or as an atomic deployment step before application traffic is enabled, instead of relying on `Base.metadata.create_all`
2. THE ERP_System startup sequence SHALL NOT execute ad hoc inline DDL (e.g. `ALTER TABLE ... ADD COLUMN`) outside of an Alembic migration
3. THE existing ad hoc schema patch (the `amount_paid` column addition) SHALL be captured as a proper Alembic migration and removed from `init_db`
4. IF a migration fails during startup or deployment, THEN THE ERP_System SHALL fail to start or the deployment SHALL be blocked and log the migration error, rather than serving traffic in a partially-migrated state

### Requirement 9: Background Task Processing

**User Story:** As a user, I want slow operations like sending emails or generating large reports to not block the HTTP request, so that the API stays responsive.

#### Acceptance Criteria

1. THE ERP_System SHALL provide a background task mechanism (e.g. ARQ or Celery with the existing Redis instance as broker) for asynchronous jobs
2. WHEN a password reset email is triggered, THE ERP_System SHALL enqueue the send as a background job rather than sending it synchronously within the request
3. THE background task mechanism SHALL support retries with backoff for transient failures (e.g. SMTP timeout)
4. THE ERP_System SHALL expose a way to inspect background job status for operational troubleshooting (e.g. a log line per job outcome at minimum)

### Requirement 10: Continuous Integration

**User Story:** As a developer, I want every change to be automatically linted, type-checked, tested, scanned, and built, so that regressions and supply-chain risks are caught before merge instead of in production.

#### Acceptance Criteria

1. THE CI_Pipeline SHALL run on every push and pull request against the main branch
2. THE CI_Pipeline SHALL run backend linting, the backend test suite (pytest, including property tests), and a backend Docker build
3. THE CI_Pipeline SHALL run frontend linting, frontend type-checking, the frontend test suite, and a frontend production build
4. THE CI_Pipeline SHALL run dependency and container vulnerability scans with documented severity thresholds and an expiring exception process
5. THE CI_Pipeline SHALL produce commit-identifiable build artifacts and retain enough metadata to identify the deployed source and migration version
6. IF any required CI_Pipeline step fails, THEN THE CI_Pipeline SHALL mark the run as failed and block merge when configured as a required check


### Requirement 11: API Documentation Availability

**User Story:** As an internal developer or integrator, I want to reach API documentation for the production deployment without exposing it publicly, so that I can debug integrations without weakening production security.

#### Acceptance Criteria

1. WHILE `environment` is `production`, THE ERP_System SHALL keep `/docs` and `/redoc` disabled for unauthenticated access
2. THE ERP_System SHALL provide an authenticated or network-restricted way to access API documentation in production (e.g. gated behind an internal-only route or Admin-role authentication)

### Requirement 12: Frontend Error Resilience

**User Story:** As a user, I want a failure in one part of the page to show a helpful fallback instead of a blank white screen, so that I can recover without losing my place in the app.

#### Acceptance Criteria

1. THE frontend SHALL wrap top-level route segments in an Error_Boundary that displays a fallback UI with a retry action when a rendering error occurs
2. WHEN an Error_Boundary catches an error, THE frontend SHALL report it to the Error_Tracker with route context
3. THE frontend SHALL provide a dedicated `not-found` and `error` page consistent with Next.js App Router conventions for every top-level route segment that currently lacks one

### Requirement 13: Frontend Server State Management

**User Story:** As a developer, I want a consistent pattern for fetching, caching, and invalidating server data in the frontend, so that loading and error states are handled the same way across every page instead of being reimplemented ad hoc.

#### Acceptance Criteria

1. THE frontend SHALL adopt a Query_Client for all server data fetching, replacing direct ad hoc `axios`/`api` calls wired to local component state
2. THE Query_Client SHALL provide consistent loading, error, and empty states available to any component consuming server data
3. WHEN a mutation (create/update/delete) succeeds, THE Query_Client SHALL invalidate or update the relevant cached queries so the UI reflects the change without a full page reload
4. THE frontend SHALL centralize API error handling (e.g. session-expired redirect, toast on failure) in one place rather than duplicating try/catch blocks per page

### Requirement 14: Frontend Form Validation

**User Story:** As a user filling out a form, I want immediate, clear feedback when my input is invalid, so that I can correct mistakes before submitting.

#### Acceptance Criteria

1. THE frontend SHALL validate form input client-side using a Form_Validator before submission, mirroring the backend's validation rules (e.g. password complexity, required fields)
2. WHEN client-side validation fails, THE frontend SHALL display field-level error messages without submitting the request
3. WHEN the backend returns a validation error, THE frontend SHALL map the error to the corresponding form field where possible, instead of showing only a generic message
4. THE Form_Validator SHALL be applied to all forms that create or update a domain entity (users, spare parts, sales, purchases, customers, suppliers, transfers)

### Requirement 15: Frontend Automated Testing

**User Story:** As a developer, I want automated frontend tests, so that I can refactor UI code with confidence that critical flows still work.

#### Acceptance Criteria

1. THE Frontend_Test_Runner SHALL support unit/component tests for shared components (`lib/api.ts`, `lib/auth.ts`, form components) using Vitest/Jest and React Testing Library
2. THE Frontend_Test_Runner SHALL support at least one end-to-end test (e.g. Playwright) covering the login flow and one core business flow (e.g. creating a sale)
3. THE CI_Pipeline SHALL execute the Frontend_Test_Runner suite on every push and pull request
4. WHEN a shared component (Token_Store, API client, Error_Boundary) changes, THE existing test suite SHALL fail if its documented behavior (e.g. token refresh queuing, redirect on auth failure) is broken

### Requirement 16: Frontend Dependency Currency

**User Story:** As a maintainer, I want the frontend framework and libraries to be reasonably current, so that the app continues to receive security patches and is not blocked from adopting new features.

#### Acceptance Criteria

1. THE ERP_System SHALL document the currently supported Next.js and React major versions and the process for upgrading them
2. WHEN a dependency upgrade is performed, THE change SHALL be verified against the full frontend test suite and a manual smoke test of the primary flows before merge
3. THIS requirement does not mandate an immediate major-version upgrade as part of this spec; it establishes the process and defers the actual upgrade to a tracked follow-up task


### Requirement 17: Backend Performance and Scalability

**User Story:** As an operator, I want the API and database access patterns to remain fast and bounded as inventory, sales, users, and locations grow, so that the application can scale predictably without exhausting resources.

#### Acceptance Criteria

1. ALL collection endpoints SHALL support bounded pagination with a documented default page size, maximum page size, stable ordering, and a response envelope containing page metadata or an equivalent cursor
2. THE ERP_System SHALL not issue unbounded database queries, load unbounded relationship collections, or perform per-row database queries for a collection response; query plans SHALL be reviewed for the highest-volume list and report endpoints to prevent N+1 access
3. THE database SHALL have indexes for documented high-cardinality filters, foreign keys used in joins, tenant-independent lookup keys currently used by the application, and common time/status queries; every new index SHALL be justified against a query or constraint
4. THE database engine and Redis clients SHALL use bounded connection pools, acquisition timeouts, command/query timeouts, and controlled concurrency so that overload fails fast instead of exhausting worker resources
5. THE ERP_System SHALL use caching only for explicitly identified safe read operations, with a defined TTL, cache-key namespace, invalidation strategy, and a fallback to the source of truth when Redis is unavailable
6. Non-idempotent operations that may be retried by clients or workers SHALL support idempotency keys or an equivalent deduplication mechanism where duplicate execution could create a sale, payment, stock movement, email, or other irreversible side effect
7. THE API SHALL expose performance telemetry for request count, error count, latency percentiles, database pool saturation, Redis errors, queue depth, and worker/job failures, with alert thresholds documented for production
8. THE application SHALL define initial performance budgets for critical API routes (including p95 latency and error rate) and critical frontend flows, and CI or staging performance checks SHALL detect material regressions
9. THE application SHALL implement graceful shutdown and bounded request/job concurrency so in-flight requests and jobs can complete or fail safely during deployments without accepting unlimited new work

### Requirement 18: Data Protection, Backup, and Recovery

**User Story:** As a business operator, I want business records and credentials protected and recoverable, so that an outage, operator error, or security incident does not cause permanent data loss.

#### Acceptance Criteria

1. Production traffic and all database, Redis, SMTP, and error-tracker connections that leave the host SHALL use TLS where supported, and production secrets SHALL be supplied by a secret manager or protected deployment environment rather than committed files
2. PostgreSQL backups SHALL run automatically on a documented schedule with encryption, retention, access controls, and an off-host or separately failure-domained copy
3. THE operations runbook SHALL define target recovery point objective (RPO), recovery time objective (RTO), restore steps, and ownership for database and uploaded/generated assets
4. THE team SHALL perform and record a restore verification at least once per release cycle or quarterly, whichever is more frequent, including integrity checks for inventory, sales, customer, supplier, and audit data
5. Logs, login history, audit trails, reset-token markers, job records, and backups SHALL have documented retention and deletion policies that preserve regulatory and operational needs while minimizing unnecessary personal data
6. Production database roles SHALL follow least privilege; application credentials SHALL not have migration or administrative privileges unless the deployment step explicitly requires a separate migration identity

### Requirement 19: Frontend Performance and Accessibility

**User Story:** As a user, I want the ERP interface to load quickly, remain responsive with large datasets, and be usable with assistive technology, so that daily operations do not slow down as data grows.

#### Acceptance Criteria

1. Critical frontend routes SHALL define budgets for initial JavaScript, route load time, and Core Web Vitals in a production-like environment; CI or staging checks SHALL detect regressions against those budgets
2. The frontend SHALL use route-level code splitting and dynamic imports for heavy or infrequently used modules, and SHALL avoid loading report/PDF/charting code on routes that do not need it
3. Data-heavy tables and lists SHALL use server-side pagination/filtering, debounced search, and virtualization or incremental rendering where appropriate; the UI SHALL not render an unbounded dataset in one browser frame
4. The frontend SHALL avoid request waterfalls by prefetching or parallelizing independent queries, use appropriately configured caching, and display useful loading/skeleton states without blocking unrelated UI
5. Images, logos, and generated documents SHALL use optimized formats, explicit dimensions, lazy loading where appropriate, and bounded payload sizes
6. Interactive workflows and shared components SHALL meet WCAG 2.1 AA-oriented practices for keyboard navigation, focus management, labels, contrast, error announcements, and screen-reader semantics
7. Critical frontend flows SHALL be tested on representative desktop and mobile viewport sizes, and performance tests SHALL run against production builds rather than development mode

### Requirement 20: Supply-Chain and Release Verification

**User Story:** As a maintainer, I want releases to be reproducible and screened for vulnerable dependencies and images, so that a production deployment does not introduce a preventable supply-chain risk.

#### Acceptance Criteria

1. Backend and frontend dependency lockfiles SHALL be committed, dependency versions SHALL be pinned or constrained by the lockfile, and CI SHALL fail on malformed or inconsistent lockfiles
2. CI SHALL run dependency vulnerability scanning and container image scanning with documented severity thresholds and an exception/expiry process for accepted risks
3. CI SHALL produce a reproducible build artifact or image tagged with the commit identifier and SHALL retain the build metadata needed to identify the deployed source
4. Release promotion SHALL require the relevant tests, security scans, migration checks, and smoke tests to pass; production deployment SHALL be auditable by commit, image, and migration version
5. The application SHALL expose only required container ports, run as a non-root user where supported, use a read-only filesystem or restricted writable paths where supported, and avoid development mounts/configuration in production images
