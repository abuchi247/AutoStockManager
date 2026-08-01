# Implementation Tasks: Production Hardening

## Task Conventions

- Complete tasks in dependency order unless a task is explicitly marked parallelizable.
- Every task that changes behavior must include focused automated tests.
- Do not add production dependencies without pinning them in the relevant lock/dependency file.
- Preserve the existing non-browser token body flow until the cookie migration is validated in staging.
- Do not remove startup schema behavior until the current database has been verified against Alembic head.

## Phase 1: Configuration, Security, and Observability Foundation

- [x] 1. Extend backend settings for production hardening
  - Add log level, request size, health timeout, refresh-cookie, SMTP, error-tracker, and job-queue settings.
  - Add safe defaults for development and require explicit production values where appropriate.
  - Update `.env.example` with descriptions and a cryptographically secure secret-generation command.
  - Requirements: 1.1, 1.2, 1.3, 2.3, 3.1, 4.3, 5.3, 6.3, 7.4, 9.1

- [x] 1.1 Add production configuration validation
  - Reject placeholder or shorter-than-32-character JWT secrets in production.
  - Reject known placeholder database passwords in production.
  - Ensure validation errors identify setting names without exposing values.
  - Add unit tests for accepted development settings and rejected production settings.
  - Requirements: 1.1, 1.2, 1.4

- [x] 2. Implement structured backend logging
  - Add JSON and development-readable formatters.
  - Include timestamp, level, logger, message, service, environment, and request ID.
  - Add secret redaction for headers, cookies, tokens, passwords, reset tokens, and database URLs.
  - Configure log verbosity from settings.
  - Add tests proving sensitive values are not emitted.
  - Requirements: 1.4, 5.1, 5.3, 5.4

- [x] 2.1 Add request ID middleware and response propagation
  - Accept a valid `X-Request-ID` or generate a UUID.
  - Store it in request state and a request-scoped logging context.
  - Return it in every response, including error responses.
  - Add tests for propagation, generation, and isolation between concurrent requests.
  - Requirements: 5.1, 5.2, 6.1

- [x] 2.2 Add global exception handling and error-tracker adapter
  - Add a no-op error tracker for local development and a Sentry-compatible implementation behind configuration.
  - Capture safe route, method, request ID, and authenticated user context.
  - Scrub authorization headers, cookies, request bodies, and secret fields.
  - Return generic 500 responses in staging/production without stack traces.
  - Add unit and integration tests for reporting and response behavior.
  - Requirements: 6.1, 6.2, 6.3, 6.4

## Phase 2: HTTP and Authentication Hardening

- [x] 3. Tighten CORS and request limits
  - Replace wildcard methods with `GET, POST, PUT, PATCH, DELETE, OPTIONS`.
  - Replace wildcard headers with the explicitly required headers.
  - Add configurable request-body size enforcement with a 5 MB default.
  - Return a stable 413 response for oversized requests, including chunked request coverage where feasible.
  - Add stricter rate limits for login, refresh, password reset, and reset confirmation routes.
  - Add tests for CORS preflight, oversized payloads, and auth rate limits.
  - Requirements: 4.1, 4.2, 4.3, 4.4

- [x] 4. Add password-reset notification abstraction
  - Define email sender and job queue protocols.
  - Implement SMTP delivery using configured settings.
  - Implement development console/log delivery without logging the raw token as a normal secret.
  - Add template/content generation for the reset URL using the configured frontend base URL.
  - Add tests for sender selection and configuration failure handling.
  - Requirements: 2.1, 2.3, 2.4

- [x] 4.1 Make password reset generic and one-time
  - Change request behavior so existing and unknown emails return the same generic success response.
  - Remove raw `reset_token` from the normal response schema.
  - Store or mark reset-token JTIs as used with an expiry matching the token.
  - Atomically reject replayed, expired, wrong-type, or malformed tokens.
  - Revoke all active sessions after successful password reset.
  - Add tests for enumeration resistance, delivery enqueueing, successful use, replay, and session revocation.
  - Requirements: 2.1, 2.2, 2.4

- [x] 5. Implement cookie-based browser refresh authentication
  - Set refresh tokens in HTTP-only, Secure, SameSite-configured cookies with a narrow path.
  - Read the cookie for refresh and logout, with a compatibility body-token path for non-browser clients.
  - Rotate the cookie and Redis session entry on refresh.
  - Expire the cookie and revoke the Redis session on logout.
  - Ensure refresh credentials are never included in JSON responses or logs.
  - Add origin/CSRF protection for cookie-authenticated state-changing requests.
  - Add backend tests for cookie attributes, precedence, rotation, logout, and compatibility behavior.
  - Requirements: 3.1, 3.3, 3.4, 3.5

- [x] 5.1 Migrate frontend token storage to memory-only access tokens
  - Remove access and refresh token persistence from `localStorage`.
  - Keep only non-sensitive user display data if needed, or remove it where server state can provide it.
  - Configure Axios with `withCredentials: true`.
  - Restore sessions on page load through a cookie-authenticated refresh request.
  - Preserve the existing concurrent refresh queue and redirect behavior.
  - Add tests proving tokens are not written to localStorage and refresh queueing remains correct.
  - Requirements: 3.2, 3.3, 3.5, 15.4

## Phase 3: Health, Migrations, and Background Jobs

- [x] 6. Upgrade health checks to verify dependencies
  - Add bounded PostgreSQL `SELECT 1` and Redis `PING` checks with concurrent timeouts.
  - Return dependency statuses and HTTP 503 when a critical dependency is down.
  - Keep response data free of credentials and internal stack traces.
  - Add tests for healthy, database-down, Redis-down, and timeout cases.
  - Requirements: 7.1, 7.2, 7.3, 7.4

- [x] 7. Establish Alembic-only schema management
  - Inspect the existing migration history and current schema for `sales.amount_paid`.
  - Add a proper Alembic revision if the column is not represented in migration history.
  - Remove `Base.metadata.create_all` and inline DDL/schema patches from application startup.
  - Add controlled migration execution to deployment/startup with failure-aborts-startup behavior.
  - Serialize migrations across multiple instances using deployment orchestration or a database advisory lock.
  - Add migration upgrade tests from the current baseline and document the operator command.
  - Requirements: 8.1, 8.2, 8.3, 8.4

- [x] 8. Add Redis-backed background task processing
  - Add the pinned ARQ dependency and worker configuration.
  - Define password-reset email and future report-generation job contracts.
  - Add retry limits and exponential backoff for transient errors.
  - Log job IDs, names, attempt counts, and safe outcomes without credentials or reset tokens.
  - Add a minimal operational status mechanism through structured job logs or a safe status endpoint.
  - Add worker unit tests and an integration test for enqueue, success, retry, and terminal failure.
  - Requirements: 9.1, 9.2, 9.3, 9.4

## Phase 4: Production Documentation and CI

- [x] 9. Add protected production API documentation access
  - Keep public `/docs` and `/redoc` disabled in production.
  - Add an Admin-protected and, where available, network-restricted documentation route.
  - Ensure the OpenAPI schema is not exposed through an unprotected alternate URL.
  - Add authorization and production configuration tests.
  - Requirements: 11.1, 11.2

- [x] 10. Add CI pipeline and quality gates
  - Add backend job for linting/formatting checks, type checks where configured, pytest, property tests, and Docker build.
  - Add frontend job for linting, TypeScript no-emit type checking, unit/component tests, and production build.
  - Add Playwright job for login and one core ERP flow using controlled test services/data.
  - Run on pushes and pull requests targeting the main branch.
  - Document required branch protection checks and local equivalents.
  - Requirements: 10.1, 10.2, 10.3, 10.4, 15.3

- [x] 10.1 Add production operations documentation
  - Document secret generation, required environment variables, migration execution, backup expectations, health endpoints, worker operation, error tracking, and rollback steps.
  - Document that credentials and CI secrets must be supplied through secret managers and never committed.
  - Document the supported frontend framework versions and dependency-upgrade checklist.
  - Requirements: 1.3, 8.1, 10.4, 16.1, 16.2, 16.3

## Phase 5: Frontend Resilience and Server State

- [x] 11. Add Next.js route error boundaries and not-found pages
  - Add root and route-group `error.tsx`/`not-found.tsx` files where needed.
  - Provide accessible fallback UI with retry/reset and navigation actions.
  - Report rendering failures with route context through the error-tracker adapter.
  - Add component tests for fallback rendering, reset, and reporting.
  - Requirements: 12.1, 12.2, 12.3, 15.1

- [x] 12. Install and configure TanStack Query
  - Add the pinned Query dependency and root QueryClient provider.
  - Set bounded stale times, retry behavior, and global error/mutation policies.
  - Create centralized query keys and typed query/mutation hook conventions.
  - Keep Axios as the sole transport and normalize errors centrally.
  - Requirements: 13.1, 13.2, 13.4

- [x] 12.1 Migrate feature pages to query hooks incrementally
  - Migrate dashboard, inventory, customers, suppliers, sales, purchases, transfers, users, and reports without changing API semantics.
  - Add loading, error, and empty states to each migrated route.
  - Invalidate or update related queries after successful mutations.
  - Remove duplicated request-side state and repeated auth/error handling from migrated components.
  - Add tests for representative queries, mutations, and cache invalidation.
  - Requirements: 13.1, 13.2, 13.3, 13.4

- [x] 13. Add React Hook Form and Zod validation layer
  - Add pinned dependencies and shared validation/error-mapping utilities.
  - Create schemas that mirror backend rules for users, spare parts, sales, purchases, customers, suppliers, and transfers.
  - Add field-level errors before submission and map FastAPI validation errors back to fields.
  - Preserve server-side validation as authoritative.
  - Add component tests for invalid input, successful submission, and backend validation mapping.
  - Requirements: 14.1, 14.2, 14.3, 14.4

## Phase 6: Frontend Test Coverage and Dependency Process

- [x] 14. Configure frontend unit and component testing
  - Add Vitest or Jest, React Testing Library, and request mocking with pinned versions.
  - Test the in-memory token store, API client, refresh queue, error normalization, error boundary, Query provider, and representative forms.
  - Add test scripts that run once in CI rather than watch mode.
  - Requirements: 15.1, 15.4

- [x] 14.1 Add Playwright end-to-end coverage
  - Add a deterministic login test with test credentials supplied by CI secrets/environment.
  - Add one core business-flow test, preferably creating a sale.
  - Configure isolated test data and service startup/cleanup.
  - Include the e2e suite in CI and document local execution.
  - Requirements: 15.2, 15.3

- [x] 15. Document and enforce frontend dependency currency
  - Record supported Next.js and React major versions.
  - Add an upgrade checklist covering dependency audit, test suite, production build, and manual primary-flow smoke test.
  - Defer major-version upgrades unless separately approved and validated.
  - Add a scheduled dependency review or update tool configuration if appropriate.
  - Requirements: 16.1, 16.2, 16.3

## Phase 7: Performance, Recovery, and Release Hardening

- [x] 17. Add bounded API query and resource-performance controls
  - Inventory all collection, dashboard, and report endpoints and define pagination, stable ordering, maximum page sizes, and filter contracts.
  - Review representative SQL query plans and remove N+1 access with projection queries or appropriate eager-loading strategies.
  - Add/verify indexes for high-volume filters, joins, foreign keys, and time/status queries based on measured plans.
  - Configure bounded database/Redis pools, acquisition timeouts, statement/command timeouts, and worker concurrency/backpressure.
  - Add tests for pagination bounds, query count/N+1 regressions, timeout behavior, and representative response budgets.
  - Requirements: 17.1, 17.2, 17.3, 17.4, 17.9

- [x] 17.1 Add caching and idempotency controls where side effects require them
  - Document safe cacheable reads, TTLs, versioned key namespaces, invalidation, and source-of-truth fallback.
  - Add idempotency keys/deduplication for retryable non-idempotent sales, stock movements, emails, and background jobs where duplicate execution is unsafe.
  - Enforce request-body consistency when an idempotency key is reused and return the original result for a valid retry.
  - Add concurrency tests proving duplicate requests/jobs do not duplicate side effects.
  - Requirements: 17.5, 17.6

- [x] 17.2 Add metrics, tracing, SLOs, and performance regression checks
  - Add a provider-neutral metrics/tracing adapter with request, dependency, database-pool, queue, and worker telemetry.
  - Propagate request/trace IDs into logs, error tracking, and background jobs while redacting sensitive fields.
  - Define initial API and frontend performance budgets, p95 latency/error thresholds, and alert ownership in the operations runbook.
  - Add production-build performance checks and document how thresholds are recalibrated from production evidence.
  - Requirements: 17.7, 17.8, 19.1, 19.7

- [x] 17.3 Implement backup, restore, retention, and least-privilege controls
  - Document RPO/RTO, backup schedule, encryption, retention, off-host storage, restore access, and ownership.
  - Separate application and migration database identities and restrict production credentials to least privilege.
  - Add an automated or scheduled restore verification into an isolated environment with integrity checks for ledgers, sales, purchases, invoices, users, and audit trails.
  - Document retention/deletion policies for logs, login history, audit trails, reset markers, jobs, backups, and personal data.
  - Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6

- [x] 17.4 Harden release artifacts and production containers
  - Commit and validate backend/frontend lockfiles.
  - Add dependency and container vulnerability scans with severity thresholds and expiring exceptions.
  - Build and retain commit-tagged artifacts with source and migration metadata.
  - Remove development mounts/default credentials, run containers as non-root, restrict writable paths, and expose only required ports.
  - Requirements: 20.1, 20.2, 20.3, 20.4, 20.5

- [x] 17.5 Implement frontend performance and accessibility budgets
  - Add route-level code splitting/dynamic imports for reports, charts, PDF/document features, and other heavy modules.
  - Migrate data-heavy lists to server pagination, debounced filtering, and virtualization/incremental rendering where appropriate.
  - Configure query prefetching/parallel requests without refetch storms and add accessible loading/error/empty state behavior.
  - Run Lighthouse or an equivalent production-build check, bundle-size tracking, representative viewport testing, and automated accessibility scans.
  - Add keyboard/focus/screen-reader tests for critical workflows and preserve table accessibility when virtualizing.
  - Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7

## Final Verification

- [x] 18. Run the complete backend and frontend validation suite
  - Run backend tests, property tests, lint/type checks, and Docker build.
  - Run frontend lint, type check, unit/component tests, production build, and Playwright tests.
  - Verify all new dependencies are pinned and lockfiles are committed.

- [x] 18.1 Perform production-like security and resilience smoke tests
  - Verify production startup rejects weak/default secrets.
  - Verify production startup aborts on migration failure.
  - Verify `/health` returns 503 when PostgreSQL or Redis is unavailable.
  - Verify password reset never returns a raw token and replay is rejected.
  - Verify refresh cookies have required attributes and browser refresh/logout work.
  - Verify oversized requests are rejected and auth endpoints have stricter limits.
  - Verify logs and error-tracker events contain no secrets.
  - Verify frontend error boundaries, session restoration, form errors, and core flow behavior.

- [x] 18.2 Review rollout and rollback readiness
  - Confirm compatibility behavior for non-browser clients.
  - Confirm database backup and migration rollback procedures.
  - Confirm worker deployment and failure handling.
  - Confirm CI required checks and production monitoring/alerting are enabled.
