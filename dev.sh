#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "==> Starting docker compose (postgres + redis)"
docker compose up -d postgres redis

echo "==> Waiting for postgres healthy"
for i in {1..30}; do
  if docker compose ps postgres | grep -q "healthy"; then
    echo "    postgres ready"
    break
  fi
  sleep 1
done

echo "==> Applying alembic migrations"
(cd backend && uv run alembic upgrade head)

echo "==> Starting backend (uvicorn)"
(cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

# echo "==> Starting celery worker"
# (cd backend && uv run celery -A app.workers.celery_app worker --loglevel=info) &
# CELERY_PID=$!

# echo "==> Starting frontend (next dev)"
# (cd frontend && pnpm dev) &
# FRONTEND_PID=$!

cleanup() {
  echo "==> Shutting down"
  kill $BACKEND_PID 2>/dev/null || true
  # kill $CELERY_PID 2>/dev/null || true
  # kill $FRONTEND_PID 2>/dev/null || true
  wait
}
trap cleanup INT TERM

echo ""
echo "Services running:"
echo "   Backend:  http://localhost:8000/api/v1/health"
# echo "   Frontend: http://localhost:3000"
echo "   Press Ctrl+C to stop"
echo ""

wait
