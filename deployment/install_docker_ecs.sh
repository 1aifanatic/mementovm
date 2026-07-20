#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this one-time host preparation script as root." >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git docker.io docker-compose-v2 unattended-upgrades
systemctl enable --now docker

if ! id deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash deploy
fi
usermod -aG docker deploy
install -d -o deploy -g deploy -m 0750 /opt/mementovm

echo "Host prepared. Add the deploy user's SSH key, clone the repository, and create /opt/mementovm/.env."

