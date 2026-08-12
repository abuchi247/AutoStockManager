#!/usr/bin/env sh
# =============================================================================
# AutoStockManager — PostgreSQL backup script
#
# POSIX sh — compatible with Alpine Linux's /bin/sh (ash/busybox).
#
# Usage:
#   sh /backup.sh
#
# Via docker compose (development, on-demand):
#   docker compose --profile backup run --rm backup
#   docker compose --profile backup run --rm -e BACKUP_LABEL=pre-release backup
#
# Via docker compose (production, scheduled — see docker-compose.production.yml):
#   Runs automatically at BACKUP_SCHEDULE (default: daily 02:00 UTC).
#
# Environment variables:
#   PGHOST        PostgreSQL host           (default: postgres)
#   PGPORT        PostgreSQL port           (default: 5432)
#   PGDATABASE    Database name             (falls back to POSTGRES_DB)
#   PGUSER        Database user             (falls back to POSTGRES_USER)
#   PGPASSWORD    Database password         (falls back to POSTGRES_PASSWORD)
#   BACKUP_DIR    Where to store dumps      (default: /backups)
#   BACKUP_RETAIN How many backups to keep  (default: 30)
#   BACKUP_LABEL  Optional filename label   (e.g. "pre-release")
#
# Output files (all in BACKUP_DIR):
#   autostockmanager-YYYY-MM-DDTHH-MM-SS[.label].dump        — pg_dump custom format
#   autostockmanager-YYYY-MM-DDTHH-MM-SS[.label].dump.sha256 — SHA-256 checksum
#   latest.dump                                              — symlink to newest backup
#   backup.log                                               — append-only run log
# =============================================================================
set -eu

PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-autostockmanager}}"
PGUSER="${PGUSER:-${POSTGRES_USER:-postgres}}"
PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-}}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETAIN="${BACKUP_RETAIN:-30}"
BACKUP_LABEL="${BACKUP_LABEL:-}"

export PGPASSWORD

# ---- Validate ----------------------------------------------------------------
if [ -z "${PGPASSWORD}" ]; then
    echo "[backup] ERROR: PGPASSWORD / POSTGRES_PASSWORD is not set" >&2
    exit 1
fi

if [ ! -d "${BACKUP_DIR}" ]; then
    mkdir -p "${BACKUP_DIR}"
fi

if [ ! -w "${BACKUP_DIR}" ]; then
    echo "[backup] ERROR: backup directory '${BACKUP_DIR}' is not writable" >&2
    exit 1
fi

# ---- Filename ----------------------------------------------------------------
TIMESTAMP="$(date -u '+%Y-%m-%dT%H-%M-%S')"
if [ -n "${BACKUP_LABEL}" ]; then
    FILENAME="autostockmanager-${TIMESTAMP}.${BACKUP_LABEL}.dump"
else
    FILENAME="autostockmanager-${TIMESTAMP}.dump"
fi
FILEPATH="${BACKUP_DIR}/${FILENAME}"
LOG_FILE="${BACKUP_DIR}/backup.log"

# ---- Log helper --------------------------------------------------------------
log() {
    msg="[backup] $(date -u '+%Y-%m-%dT%H:%M:%SZ') $*"
    echo "${msg}"
    echo "${msg}" >> "${LOG_FILE}"
}

log "Starting: database=${PGDATABASE} host=${PGHOST}:${PGPORT} file=${FILENAME}"

# ---- pg_dump -----------------------------------------------------------------
if ! pg_dump \
        --host="${PGHOST}" \
        --port="${PGPORT}" \
        --username="${PGUSER}" \
        --dbname="${PGDATABASE}" \
        --format=custom \
        --no-owner \
        --no-acl \
        --file="${FILEPATH}"; then
    log "ERROR: pg_dump failed — removing partial file"
    rm -f "${FILEPATH}"
    exit 1
fi

BACKUP_SIZE="$(du -sh "${FILEPATH}" | cut -f1)"
log "pg_dump complete: size=${BACKUP_SIZE}"

# ---- Checksum ----------------------------------------------------------------
CHECKSUM_FILE="${FILEPATH}.sha256"
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${FILEPATH}" > "${CHECKSUM_FILE}"
    CHECKSUM="$(cut -d' ' -f1 "${CHECKSUM_FILE}")"
    log "Checksum: sha256=${CHECKSUM}"
elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${FILEPATH}" > "${CHECKSUM_FILE}"
    CHECKSUM="$(cut -d' ' -f1 "${CHECKSUM_FILE}")"
    log "Checksum: sha256=${CHECKSUM}"
else
    log "WARNING: sha256sum / shasum not found — checksum skipped"
fi

# ---- Latest symlink ----------------------------------------------------------
ln -sf "${FILEPATH}" "${BACKUP_DIR}/latest.dump"
log "Symlink updated: latest.dump -> ${FILEPATH}"

# ---- Retention ---------------------------------------------------------------
# Count existing dumps; delete oldest ones beyond the retain limit.
TOTAL=$(find "${BACKUP_DIR}" -maxdepth 1 -name "autostockmanager-*.dump" \
          ! -name "*.sha256" | wc -l | tr -d ' ')
DELETE_COUNT=$((TOTAL - BACKUP_RETAIN))

if [ "${DELETE_COUNT}" -gt 0 ]; then
    log "Retention: keeping ${BACKUP_RETAIN} of ${TOTAL}, removing ${DELETE_COUNT} old backup(s)"
    find "${BACKUP_DIR}" -maxdepth 1 -name "autostockmanager-*.dump" \
        ! -name "*.sha256" | sort | head -n "${DELETE_COUNT}" | while read -r OLD; do
        log "Removing: ${OLD}"
        rm -f "${OLD}" "${OLD}.sha256"
    done
fi

# ---- Summary -----------------------------------------------------------------
REMAINING=$(find "${BACKUP_DIR}" -maxdepth 1 -name "autostockmanager-*.dump" \
              ! -name "*.sha256" | wc -l | tr -d ' ')
log "Done. Retained ${REMAINING}/${BACKUP_RETAIN} backup(s)."
log "---"
