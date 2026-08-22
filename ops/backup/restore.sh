#!/usr/bin/env sh
set -eu

: "${DATABASE_RESTORE_URL:?Set DATABASE_RESTORE_URL to the target postgresql:// URL}"
: "${1:?Usage: restore.sh /path/to/drovixa.dump}"

BACKUP_FILE="$1"
if [ "${CONFIRM_RESTORE:-}" != "DROVIXA" ]; then
  echo "Set CONFIRM_RESTORE=DROVIXA after reviewing the target database." >&2
  exit 1
fi
if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi
if [ -f "${BACKUP_FILE}.sha256" ]; then
  sha256sum -c "${BACKUP_FILE}.sha256"
fi

pg_restore --dbname="$DATABASE_RESTORE_URL" --clean --if-exists --no-owner --no-privileges "$BACKUP_FILE"
echo "Restore completed. Run health, login, catalog, and playback smoke tests now."
