#!/usr/bin/env bash

AGENT="$1"

TASKS="shared/current/tasks.md"
STATUS="shared/current/status.md"
REVIEW="shared/current/review.md"
NEXT="shared/current/next-action.md"
OUT="shared/current/agent-context.md"

TASK=$(grep -m1 "^### Task-" "$TASKS" | sed 's/^### //')
STATE=$(grep -m1 "^状态:" "$TASKS" | sed 's/^状态:[[:space:]]*//')
OWNER=$(grep -m1 "^负责人:" "$TASKS" | sed 's/^负责人:[[:space:]]*//')
NEXT_AGENT=$(grep -m1 "^Agent:" "$NEXT" | sed 's/^Agent:[[:space:]]*//')

{
  echo "# Agent Context"
  echo
  echo "Generated at: $(date)"
  echo
  echo "## Current Agent"
  echo
  echo "$AGENT"
  echo
  echo "## Next Action"
  echo
  cat "$NEXT"
  echo
  echo "## Current Task"
  echo
  echo "- Task: $TASK"
  echo "- State: $STATE"
  echo "- Owner: $OWNER"
  echo
  echo "## Role Instructions"
  echo
  cat "agents/$AGENT.md"
  echo
  echo "## Tasks"
  echo
  cat "$TASKS"
  echo
  echo "## Status"
  echo
  cat "$STATUS"
  echo
  echo "## Review"
  if [ -f "$REVIEW" ]; then
    cat "$REVIEW"
  else
    echo "No review file found."
  fi
  echo
  echo "## Decisions"
  if ls shared/decisions/* >/dev/null 2>&1; then
    cat shared/decisions/*
  else
    echo "No decisions found."
  fi
} > "$OUT"

echo "Generated: $OUT"