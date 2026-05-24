#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if ! docker compose ps postgres redis >/dev/null 2>&1; then
  echo "Docker Compose is not available. Start Docker Desktop first." >&2
  exit 1
fi

docker compose up -d postgres redis
exec claude
