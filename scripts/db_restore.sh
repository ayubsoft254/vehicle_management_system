#!/bin/bash
# =============================================================================
# VMS Database Restore Script
# Usage: ./scripts/db_restore.sh <backup_file.sql.gz>
#
# To also restore media files run:
#   ./scripts/db_restore.sh backups/db_20260101_020000.sql.gz \
#                           backups/media_20260101_020000.tar.gz
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

# Load environment
if [ -f "$ENV_FILE" ]; then
    set -o allexport
    # shellcheck disable=SC1090
    source <(grep -v '^#' "$ENV_FILE" | grep -v '^[[:space:]]*$')
    set +o allexport
fi

DB_CONTAINER="${DB_CONTAINER:-vms_db}"
DB_NAME="${DB_NAME:-vms_db}"
DB_USER="${DB_USER:-vms_user}"
BACKUP_DIR="$PROJECT_DIR/backups"

DB_BACKUP_FILE="${1:-}"
MEDIA_BACKUP_FILE="${2:-}"

# ── Show usage if no argument ──────────────────────────────────────────────
if [ -z "$DB_BACKUP_FILE" ]; then
    echo "Usage: $0 <db_backup.sql.gz> [media_backup.tar.gz]"
    echo ""
    echo "Available DB backups:"
    find "$BACKUP_DIR" -name "db_*.sql.gz" -type f 2>/dev/null \
        | sort -r | head -10 \
        | while read -r f; do
            echo "  $(du -h "$f" | cut -f1)  $f  ($(date -r "$f" '+%Y-%m-%d %H:%M'))"
        done || echo "  No backups found in $BACKUP_DIR"
    exit 0
fi

if [ ! -f "$DB_BACKUP_FILE" ]; then
    echo "ERROR: File not found: $DB_BACKUP_FILE"
    exit 1
fi

# ── Confirm ────────────────────────────────────────────────────────────────
echo ""
echo "  WARNING: This will REPLACE the current '$DB_NAME' database."
echo "  Backup to restore: $DB_BACKUP_FILE"
if [ -n "$MEDIA_BACKUP_FILE" ]; then
    echo "  Media to restore:  $MEDIA_BACKUP_FILE"
fi
echo ""
read -rp "  Type 'yes' to continue: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# ── Check container ────────────────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    echo "ERROR: Container '$DB_CONTAINER' is not running."
    exit 1
fi

# ── Take a safety backup of current state first ────────────────────────────
echo ""
echo "Creating safety backup of current database before restore..."
SAFETY_FILE="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"
mkdir -p "$BACKUP_DIR"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" --no-password "$DB_NAME" \
    | gzip > "$SAFETY_FILE" \
    && echo "Safety backup saved: $SAFETY_FILE" \
    || echo "WARNING: Could not create safety backup (proceeding anyway)"

# ── Drop existing connections and recreate database ────────────────────────
echo ""
echo "Dropping connections to '$DB_NAME'..."
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" \
    > /dev/null 2>&1 || true

echo "Dropping and recreating database..."
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS \"$DB_NAME\";"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres \
    -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";"

# ── Restore ────────────────────────────────────────────────────────────────
echo "Restoring database from $DB_BACKUP_FILE..."
if gunzip -c "$DB_BACKUP_FILE" \
    | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" --quiet; then
    echo "Database restored successfully."
else
    echo ""
    echo "ERROR: Restore failed. Your pre-restore backup is at:"
    echo "  $SAFETY_FILE"
    exit 1
fi

# ── Media restore (optional) ───────────────────────────────────────────────
if [ -n "$MEDIA_BACKUP_FILE" ]; then
    if [ ! -f "$MEDIA_BACKUP_FILE" ]; then
        echo "WARNING: Media backup file not found: $MEDIA_BACKUP_FILE (skipping)"
    else
        echo ""
        echo "Restoring media files from $MEDIA_BACKUP_FILE..."
        MEDIA_PARENT="$PROJECT_DIR/src"
        rm -rf "$MEDIA_PARENT/media"
        tar -xzf "$MEDIA_BACKUP_FILE" -C "$MEDIA_PARENT"
        echo "Media files restored."
    fi
fi

echo ""
echo "Restore complete. You may need to restart the application:"
echo "  docker compose restart web celery_worker"
