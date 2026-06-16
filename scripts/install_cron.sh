#!/bin/bash
# =============================================================================
# Install the daily backup cron job on the production server.
# Run once after deployment: sudo bash scripts/install_cron.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/db_backup.sh"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/backups/backup.log"

# Make scripts executable
chmod +x "$BACKUP_SCRIPT"
chmod +x "$SCRIPT_DIR/db_restore.sh"

# Cron schedule: 2:00 AM daily
CRON_JOB="0 2 * * * $BACKUP_SCRIPT >> $LOG_FILE 2>&1"

echo "Installing backup cron job..."

if crontab -l 2>/dev/null | grep -qF "$BACKUP_SCRIPT"; then
    echo "Cron job already installed — no changes made."
else
    (crontab -l 2>/dev/null || true; echo "$CRON_JOB") | crontab -
    echo "Cron job installed: daily backup at 02:00 AM."
fi

echo ""
echo "Current crontab:"
crontab -l

echo ""
echo "Test the backup script now with:"
echo "  $BACKUP_SCRIPT"
echo ""
echo "View backup logs with:"
echo "  tail -f $LOG_FILE"
