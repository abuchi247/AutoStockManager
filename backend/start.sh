#!/bin/sh
###############################################################################
# Backend container startup script
#
# 1. Runs database migrations (unless RUN_MIGRATIONS=false).
# 2. Starts uvicorn with multiple workers for real concurrency.
#
# Worker count is configurable via WEB_CONCURRENCY (defaults to 2). On a
# multi-core host, set WEB_CONCURRENCY to roughly (2 x CPU cores) + 1, capped
# by available memory. A single worker serializes all requests on one event
# loop, which is the main cause of "feels slow" under concurrent load.
###############################################################################
set -e

# Run migrations unless explicitly disabled (e.g. when a separate release
# step already applied them). Migration failure aborts startup.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head
fi

WORKERS="${WEB_CONCURRENCY:-2}"
echo "Starting uvicorn with ${WORKERS} worker(s)..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "${WORKERS}" \
  --no-access-log
