#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/mementovm}"
COMPOSE_FILE="docker-compose.prod.yml"

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Run as the non-root deploy user." >&2
  exit 1
fi

for command in docker git curl; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 1; }
done

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "Clone the repository to $APP_DIR before running this script." >&2
  exit 1
fi

cd "$APP_DIR"
test -f .env || { echo "Missing $APP_DIR/.env" >&2; exit 1; }

git fetch --tags --prune
if [[ -n "${DEPLOY_REF:-}" ]]; then
  git checkout --detach "$DEPLOY_REF"
fi

docker compose -f "$COMPOSE_FILE" build --pull
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
docker compose -f "$COMPOSE_FILE" exec -T backend alembic -c backend/alembic.ini upgrade head
docker compose -f "$COMPOSE_FILE" ps

PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost}"
curl --fail --silent --show-error "$PUBLIC_BASE_URL/healthz"
curl --fail --silent --show-error "$PUBLIC_BASE_URL/readyz"
echo "Deployment verified at $PUBLIC_BASE_URL"

