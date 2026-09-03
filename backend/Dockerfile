###############################################################################
# Production Dockerfile for AutoStockManager backend
# - Multi-stage build for smaller image
# - Runs as non-root user
# - No development mounts or default credentials
# - Only exposes required port
###############################################################################

# ---------- Stage 1: Builder ----------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

# Install build-time system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel "jaraco.context>=6.1.0" && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Stage 2: Runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install only runtime system libraries (no compilers/build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy application code (no volume mounts in production)
COPY --chown=appuser:appuser . .

# Create writable directories for tmp and any runtime data; restrict others
RUN mkdir -p /app/tmp && chown appuser:appuser /app/tmp

# Switch to non-root user
USER appuser

# Expose only the application port
EXPOSE 8000

# Docker-level health check so orchestrators (ECS, Swarm, Kubernetes liveness
# probes via exec) can detect a stuck or crashed process without an external
# probe service. The /health endpoint performs DB + Redis readiness checks.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Build metadata labels (overridden at build time via --build-arg)
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
ARG MIGRATION_HEAD=unknown
LABEL org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/autostockmanager/backend" \
      com.autostockmanager.migration-head="${MIGRATION_HEAD}"

# Start via the startup script: runs migrations (unless RUN_MIGRATIONS=false)
# then launches uvicorn with WEB_CONCURRENCY workers for real concurrency.
CMD ["sh", "/app/start.sh"]
