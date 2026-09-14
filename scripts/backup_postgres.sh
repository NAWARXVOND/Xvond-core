#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:=5432}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${BACKUP_DIR:=/backups}"
: "${BACKUP_STATUS_DIR:=/backup-status}"
: "${BACKUP_RETENTION_DAYS:=14}"

umask 077
mkdir -p "$BACKUP_DIR" "$BACKUP_STATUS_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
final_path="$BACKUP_DIR/xvond_${timestamp}.dump"
partial_path="${final_path}.partial"

cleanup() {
    rm -f "$partial_path"
}
trap cleanup EXIT INT TERM

pg_dump \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname="$PGDATABASE" \
    --format=custom \
    --compress=9 \
    --no-owner \
    --no-privileges \
    --file="$partial_path"

mv "$partial_path" "$final_path"
sha256sum "$final_path" > "${final_path}.sha256"

# Publish health only after the dump is complete and checksummed. Write via a
# temporary file so the app never observes a partially-written status marker.
status_tmp="$BACKUP_STATUS_DIR/local_success_epoch.partial"
printf '%s\n' "$(date -u +%s)" > "$status_tmp"
mv "$status_tmp" "$BACKUP_STATUS_DIR/local_success_epoch"

find "$BACKUP_DIR" \
    -type f \
    \( -name 'xvond_*.dump' -o -name 'xvond_*.dump.sha256' \) \
    -mtime "+$BACKUP_RETENTION_DAYS" \
    -delete

printf 'Backup completed: %s\n' "$final_path"
