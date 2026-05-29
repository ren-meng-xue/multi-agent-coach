#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

TASKS="$ROOT/shared/current/tasks.md"

STATE=$(grep -m1 "^状态:" "$TASKS" | sed 's/^状态:[[:space:]]*//')

case "$STATE" in

  pending)
    "$ROOT/scripts/dispatcher.sh"
    ;;

  in-progress)
    "$ROOT/scripts/dispatcher.sh"
    ;;

  review)
    "$ROOT/scripts/review-hook.sh"
    ;;

  done)
    "$ROOT/scripts/archive-hook.sh"
    ;;

  *)
    echo "No action for state: $STATE"
    ;;
esac