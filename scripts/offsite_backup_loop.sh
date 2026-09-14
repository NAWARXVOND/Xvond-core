#!/bin/sh
set -eu

: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required}"
: "${BACKUP_STATUS_DIR:=/backup-status}"
: "${OFFSITE_BACKUP_INTERVAL_SECONDS:=86400}"
: "${OFFSITE_KEEP_DAILY:=14}"
: "${OFFSITE_KEEP_WEEKLY:=8}"
: "${OFFSITE_KEEP_MONTHLY:=12}"

umask 077
mkdir -p "$BACKUP_STATUS_DIR"

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
    status_tmp="$BACKUP_STATUS_DIR/offsite_success_epoch.partial"
    printf '%s\n' "$(date -u +%s)" > "$status_tmp"
    mv "$status_tmp" "$BACKUP_STATUS_DIR/offsite_success_epoch"
    printf 'Encrypted offsite backup completed and repository checked.\n'
    sleep "$OFFSITE_BACKUP_INTERVAL_SECONDS"
done
