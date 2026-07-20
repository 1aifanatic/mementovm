#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/backup.sql.gz" >&2
  exit 1
fi

BACKUP_FILE="$1"
APP_DIR="${APP_DIR:-/opt/mementovm}"
[[ "$BACKUP_FILE" = /* && -f "$BACKUP_FILE" ]] || { echo "Backup must be an existing absolute path." >&2; exit 1; }
cd "$APP_DIR"
gzip -dc "$BACKUP_FILE" | docker compose -f docker-compose.prod.yml exec -T postgres psql -U memento memento
echo "Restore complete from $BACKUP_FILE"

