#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NEXT_ACTION="$ROOT/shared/current/next-action.md"
TASKS="$ROOT/shared/current/tasks.md"
STATUS="$ROOT/shared/current/status.md"
REVIEW="$ROOT/shared/current/review.md"
HEALTH="$ROOT/shared/current/.cockpit-health.md"

MAX_LINES=80
printed=0

section() {
  local title="$1"
  printf '\n═══ %s ═══\n' "$title"
  printed=$((printed + 1))
}

check_truncate() {
  if [ $printed -ge $MAX_LINES ]; then
    echo "... (truncated, see shared/current/<file>)"
    exit 0
  fi
}

# next-action
section "next-action"
check_truncate
if [ -f "$NEXT_ACTION" ]; then
  cat "$NEXT_ACTION"
  printed=$((printed + $(cat "$NEXT_ACTION" | wc -l)))
fi

# tasks (active only, non-done)
section "tasks (active)"
check_truncate
if [ -f "$TASKS" ]; then
  awk '/^### Task-/{tid=$0} /^类型:/{t=$0} /^状态:/{s=$0} /^负责人:/{o=$0} /^priority:/{p=$0} /^depends_on:/{d=$0} /^### /&&found{print tid"\n"t"\n"s"\n"o"\n"p"\n"d"\n"; found=0} /^状态:[[:space:]]*done/&&found{found=0; next} /^### Task-/{found=1; tid=$0; t=""; s=""; o=""; p=""; d=""} END{if(found && s!~/done/) print tid"\n"t"\n"s"\n"o"\n"p"\n"d}' "$TASKS"
fi

# status (last 15)
section "status (last 15)"
check_truncate
if [ -f "$STATUS" ]; then
  tail -15 "$STATUS"
  printed=$((printed + 15))
fi

# review
section "review (current)"
check_truncate
if [ -f "$REVIEW" ]; then
  cat "$REVIEW"
  printed=$((printed + $(cat "$REVIEW" | wc -l)))
fi

# dependency graph (from next-action.md)
section "dependency graph"
check_truncate
if [ -f "$NEXT_ACTION" ]; then
  awk '/^## Dependency graph/{found=1; next} found{print}' "$NEXT_ACTION" | head -20
  printed=$((printed + 20))
fi

# health
section "health (last 5)"
check_truncate
if [ -f "$HEALTH" ] && [ -s "$HEALTH" ]; then
  tail -5 "$HEALTH"
  printed=$((printed + 5))
else
  echo "(no warnings)"
  printed=$((printed + 1))
fi
