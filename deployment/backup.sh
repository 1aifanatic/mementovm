#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/mementovm}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump --clean --if-exists --no-owner -U memento memento | gzip > "$BACKUP_DIR/memento-$timestamp.sql.gz"
echo "$BACKUP_DIR/memento-$timestamp.sql.gz"

