#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:=5432}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${BACKUP_FILE:?BACKUP_FILE is required}"

if [ "${CONFIRM_RESTORE:-}" != "RESTORE_XVOND_DATABASE" ]; then
    printf '%s\n' \
        'Restore blocked. Set CONFIRM_RESTORE=RESTORE_XVOND_DATABASE.'
    exit 2
fi

resolved_path="$(realpath "$BACKUP_FILE")"

case "$resolved_path" in
    /backups/*.dump) ;;
    *)
        printf '%s\n' 'Restore blocked: backup must be inside /backups.'
        exit 2
        ;;
esac

if [ ! -f "$resolved_path" ]; then
    printf 'Restore blocked: file not found: %s\n' "$resolved_path"
    exit 2
fi

checksum_file="${resolved_path}.sha256"

if [ ! -f "$checksum_file" ]; then
    printf '%s\n' 'Restore blocked: checksum file is missing.'
    exit 2
fi

sha256sum --check "$checksum_file"

pg_restore \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --dbname="$PGDATABASE" \
    --clean \
    --if-exists \
    --exit-on-error \
    --single-transaction \
    --no-owner \
    --no-privileges \
    "$resolved_path"

printf 'Restore completed from: %s\n' "$resolved_path"
