###############################################################################
# Production Dockerfile for AutoStockManager frontend
# - Multi-stage build: deps → build → runtime
# - Runs as non-root user
# - No development mounts or default credentials
# - Only exposes required port
###############################################################################

# ---------- Stage 1: Dependencies ----------
FROM node:20-alpine3.22 AS deps

WORKDIR /app

# Copy lockfile and manifest for reproducible install
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# ---------- Stage 2: Build ----------
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build metadata available at build time
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
ENV NEXT_PUBLIC_BUILD_COMMIT=${GIT_COMMIT}
ENV NEXT_PUBLIC_BUILD_DATE=${BUILD_DATE}

RUN npm run build

# ---------- Stage 3: Runtime ----------
FROM node:20-alpine3.22 AS runtime

ENV NODE_ENV=production

# Apply latest OS security patches before locking the image down
RUN apk update && apk upgrade --no-cache && rm -rf /var/cache/apk/*

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy only production artifacts
COPY --from=builder --chown=appuser:appgroup /app/.next/standalone ./
COPY --from=builder --chown=appuser:appgroup /app/.next/static ./.next/static
COPY --from=builder --chown=appuser:appgroup /app/public ./public

# Switch to non-root user
USER appuser

# Expose only the application port
EXPOSE 3000

# Build metadata labels
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/autostockmanager/frontend"

# Start the optimized production server
CMD ["node", "server.js"]
