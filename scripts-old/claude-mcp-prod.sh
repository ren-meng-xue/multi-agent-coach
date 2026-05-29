#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.claude-mcp-prod.local"

cd "${PROJECT_ROOT}"

EXISTING_PROD_DATABASE_URL="${PROD_DATABASE_URL:-}"
EXISTING_PROD_REDIS_URL="${PROD_REDIS_URL:-}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -n "${EXISTING_PROD_DATABASE_URL}" ]]; then
  export PROD_DATABASE_URL="${EXISTING_PROD_DATABASE_URL}"
fi

if [[ -n "${EXISTING_PROD_REDIS_URL}" ]]; then
  export PROD_REDIS_URL="${EXISTING_PROD_REDIS_URL}"
fi

missing=()

if [[ -z "${PROD_DATABASE_URL:-}" || "${PROD_DATABASE_URL}" == *"REPLACE_ME"* ]]; then
  missing+=("PROD_DATABASE_URL")
fi

if [[ -z "${PROD_REDIS_URL:-}" || "${PROD_REDIS_URL}" == *"REPLACE_ME"* ]]; then
  missing+=("PROD_REDIS_URL")
fi

if (( ${#missing[@]} > 0 )); then
  echo "Missing production MCP environment variables: ${missing[*]}" >&2
  echo "Edit ${ENV_FILE} and set the real production URLs, then rerun this script." >&2
  echo "Template: ${PROJECT_ROOT}/.env.claude-mcp-prod.example" >&2
  exit 1
fi

if [[ "${ALLOW_PROD_MCP:-}" != "1" ]]; then
  echo "WARNING: You are about to start Claude Code with production MCP access." >&2
  echo "This session can use postgres-prod and redis-prod. Use read-only production credentials." >&2
  if ! read -r -p "Type 'prod' to continue: " confirmation; then
    echo "Aborted. Production MCP was not started." >&2
    exit 1
  fi

  if [[ "${confirmation}" != "prod" ]]; then
    echo "Aborted. Production MCP was not started." >&2
    exit 1
  fi
fi

exec claude
