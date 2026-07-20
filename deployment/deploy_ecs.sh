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

set -a
# The operator-created file is the deployment's trusted secret source.
# shellcheck disable=SC1091
source .env
set +a

[[ "${APP_ENV:-}" == "production" ]] || {
  echo "APP_ENV must be production for an ECS release." >&2
  exit 1
}
for variable in POSTGRES_PASSWORD APP_SECRET_KEY EVENT_INGEST_API_KEY DASHSCOPE_API_KEY; do
  value="${!variable:-}"
  if [[ ${#value} -lt 16 || "$value" == change-* ]]; then
    echo "$variable is missing or still uses a placeholder." >&2
    exit 1
  fi
done

for variable in ALIBABA_CLOUD_OSS_REGION ALIBABA_CLOUD_OSS_ENDPOINT ALIBABA_CLOUD_OSS_BUCKET; do
  if [[ -z "${!variable:-}" ]]; then
    echo "$variable is required for the production OSS proof." >&2
    exit 1
  fi
done

if [[ -z "${ALIBABA_CLOUD_ECS_RAM_ROLE:-}" ]]; then
  if [[ -z "${ALIBABA_CLOUD_ACCESS_KEY_ID:-}" || -z "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:-}" ]]; then
    echo "Set ALIBABA_CLOUD_ECS_RAM_ROLE or a least-privilege OSS AccessKey pair." >&2
    exit 1
  fi
fi

[[ "${PUBLIC_BASE_URL:-}" == https://* ]] || {
  echo "PUBLIC_BASE_URL must use HTTPS for the public release." >&2
  exit 1
}
[[ -n "${PUBLIC_DOMAIN:-}" && "${PUBLIC_DOMAIN}" != "localhost" ]] || {
  echo "PUBLIC_DOMAIN must be a public hostname for the production release." >&2
  exit 1
}

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
