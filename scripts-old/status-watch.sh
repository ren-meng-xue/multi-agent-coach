#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

while true; do

  "$SCRIPT_DIR/state-router.sh"

  clear

  echo "===== STATE DASHBOARD ====="
  echo

  cat shared/current/next-action.md 2>/dev/null || echo "no next-action"

  echo
  echo "===== STATUS ====="
  cat shared/current/status.md 2>/dev/null || echo "no status"

  echo
  echo "===== TASKS ====="
  if [ -f shared/current/tasks.md ]; then
    grep -n "Task-\|状态:\|负责人:" shared/current/tasks.md
  fi

  echo
  echo "===== REVIEW ====="
  cat shared/current/review.md 2>/dev/null || echo "no review"

  sleep 2
done