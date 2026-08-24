#!/bin/sh
set -eu

: "${BACKUP_INTERVAL_SECONDS:=86400}"

while true; do
    /opt/xvond/scripts/backup_postgres.sh
    sleep "$BACKUP_INTERVAL_SECONDS"
done
