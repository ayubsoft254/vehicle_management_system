#!/bin/bash
# =============================================================================
# VMS Database Backup Script
# Usage: ./scripts/db_backup.sh [--no-media]
# Runs automatically via cron (see scripts/install_cron.sh)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

# Load environment variables from .env
if [ -f "$ENV_FILE" ]; then
    set -o allexport
    # shellcheck disable=SC1090
    source <(grep -v '^#' "$ENV_FILE" | grep -v '^[[:space:]]*$')
    set +o allexport
fi

# Configuration — override any of these in .env
DB_CONTAINER="${DB_CONTAINER:-vms_db}"
DB_NAME="${DB_NAME:-vms_db}"
DB_USER="${DB_USER:-vms_user}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
MEDIA_DIR="$PROJECT_DIR/src/media"
SKIP_MEDIA="${1:-}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_BACKUP_FILE="$BACKUP_DIR/db_${TIMESTAMP}.sql.gz"
MEDIA_BACKUP_FILE="$BACKUP_DIR/media_${TIMESTAMP}.tar.gz"
LOG_FILE="$BACKUP_DIR/backup.log"

mkdir -p "$BACKUP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Backup started"

# ── 1. Check the container is running ──────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    log "ERROR: Container '$DB_CONTAINER' is not running. Is Docker Compose up?"
    exit 1
fi

# ── 2. PostgreSQL dump ─────────────────────────────────────────────────────
log "Dumping database '$DB_NAME'..."
if docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" --no-password "$DB_NAME" \
    | gzip > "$DB_BACKUP_FILE"; then
    SIZE=$(du -h "$DB_BACKUP_FILE" | cut -f1)
    log "DB backup OK  →  $DB_BACKUP_FILE  ($SIZE)"
else
    log "ERROR: pg_dump failed"
    rm -f "$DB_BACKUP_FILE"
    exit 1
fi

# ── 3. Media files backup ──────────────────────────────────────────────────
if [ "$SKIP_MEDIA" != "--no-media" ] && [ -d "$MEDIA_DIR" ]; then
    log "Archiving media files..."
    if tar -czf "$MEDIA_BACKUP_FILE" -C "$PROJECT_DIR/src" media 2>/dev/null; then
        SIZE=$(du -h "$MEDIA_BACKUP_FILE" | cut -f1)
        log "Media backup OK  →  $MEDIA_BACKUP_FILE  ($SIZE)"
    else
        log "WARNING: Media backup failed (continuing)"
        rm -f "$MEDIA_BACKUP_FILE"
    fi
else
    log "Skipping media backup"
fi

# ── 4. Rotate old backups ─────────────────────────────────────────────────
DELETED=$(find "$BACKUP_DIR" \( -name "db_*.sql.gz" -o -name "media_*.tar.gz" \) \
    -mtime +"$RETENTION_DAYS" -type f 2>/dev/null || true)
if [ -n "$DELETED" ]; then
    echo "$DELETED" | xargs rm -f
    COUNT=$(echo "$DELETED" | wc -l)
    log "Rotated $COUNT old file(s) older than $RETENTION_DAYS days"
fi

# ── 5. Summary ────────────────────────────────────────────────────────────
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "db_*.sql.gz" | wc -l)
log "Backup complete. $BACKUP_COUNT backup(s) on hand."
log "=========================================="
