#!/bin/sh
set -eu

: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required}"
: "${RESTORE_DIR:=/restore}"

rm -rf "$RESTORE_DIR"
mkdir -p "$RESTORE_DIR"

restic restore latest \
    --tag xvond-postgres \
    --target "$RESTORE_DIR"

backup_root="$RESTORE_DIR/backups"
if [ ! -d "$backup_root" ]; then
    printf 'Restored snapshot does not contain /backups.\n' >&2
    exit 1
fi

latest_dump="$(find "$backup_root" -type f -name 'xvond_*.dump' | sort | tail -n 1)"
if [ -z "$latest_dump" ]; then
    printf 'No PostgreSQL dump found in restored snapshot.\n' >&2
    exit 1
fi

checksum_file="${latest_dump}.sha256"
if [ ! -f "$checksum_file" ]; then
    printf 'Checksum file is missing for %s.\n' "$latest_dump" >&2
    exit 1
fi

(
    cd "$(dirname "$latest_dump")"
    sha256sum -c "$(basename "$checksum_file")"
)

printf 'Offsite restore verified: %s\n' "$latest_dump"
