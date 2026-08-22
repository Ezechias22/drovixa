#!/usr/bin/env sh
set -eu

: "${DATABASE_BACKUP_URL:?Set DATABASE_BACKUP_URL to a postgresql:// URL}"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/drovixa}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="${BACKUP_DIR}/drovixa-${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"
umask 077
pg_dump --dbname="$DATABASE_BACKUP_URL" --format=custom --compress=9 --file="$OUTPUT"
sha256sum "$OUTPUT" > "${OUTPUT}.sha256"

if [ -n "${BACKUP_S3_URI:-}" ]; then
  command -v aws >/dev/null 2>&1 || {
    echo "aws CLI is required when BACKUP_S3_URI is set" >&2
    exit 1
  }
  aws s3 cp "$OUTPUT" "${BACKUP_S3_URI}/$(basename "$OUTPUT")" --only-show-errors
  aws s3 cp "${OUTPUT}.sha256" "${BACKUP_S3_URI}/$(basename "${OUTPUT}.sha256")" --only-show-errors
fi

find "$BACKUP_DIR" -type f -name 'drovixa-*.dump*' -mtime "+$RETENTION_DAYS" -delete
echo "Backup completed: $OUTPUT"
