#!/bin/sh
set -eu

: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required}"
: "${OFFSITE_BACKUP_INTERVAL_SECONDS:=86400}"
: "${OFFSITE_KEEP_DAILY:=14}"
: "${OFFSITE_KEEP_WEEKLY:=8}"
: "${OFFSITE_KEEP_MONTHLY:=12}"

if ! restic snapshots >/dev/null 2>&1; then
    printf 'Restic repository is not initialized or is not readable; attempting initialization...\n'
    restic init
fi

while true; do
    printf 'Starting encrypted offsite backup...\n'
    restic backup /backups \
        --tag xvond-postgres \
        --host xvond-production

    restic forget \
        --tag xvond-postgres \
        --keep-daily "$OFFSITE_KEEP_DAILY" \
        --keep-weekly "$OFFSITE_KEEP_WEEKLY" \
        --keep-monthly "$OFFSITE_KEEP_MONTHLY" \
        --prune

    restic check
    printf 'Encrypted offsite backup completed and repository checked.\n'
    sleep "$OFFSITE_BACKUP_INTERVAL_SECONDS"
done
