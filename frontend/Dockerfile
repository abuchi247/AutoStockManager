###############################################################################
# Production Dockerfile for StockPilot frontend
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
FROM node:20-alpine3.22 AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build metadata available at build time
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
ENV NEXT_PUBLIC_BUILD_COMMIT=${GIT_COMMIT}
ENV NEXT_PUBLIC_BUILD_DATE=${BUILD_DATE}

# The API URL is a NEXT_PUBLIC_ var baked into the browser bundle at build
# time, so it must be provided as a build argument (not just a runtime env).
# Set this build arg to the backend's public URL, e.g.
# https://api.yourdomain.com/api/v1  (or https://yourdomain.com/api/v1 when
# the API is proxied under the same domain as the frontend).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

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
      org.opencontainers.image.source="https://github.com/abuchi247/StockPilot"

# Start the optimized production server
CMD ["node", "server.js"]
