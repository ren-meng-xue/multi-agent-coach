#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

TASKS="$ROOT/shared/current/tasks.md"
OUT="$ROOT/shared/current/next-action.md"

mkdir -p "$ROOT/shared/current"

if [ ! -f "$TASKS" ]; then
  cat > "$OUT" <<EOM
# Next Action

Agent: none
Task: none
Reason: shared/current/tasks.md not found
EOM
  exit 0
fi

TASK=$(grep -m1 "^### Task-" "$TASKS" | sed 's/^### //')
STATE=$(grep -m1 "^状态:" "$TASKS" | sed 's/^状态:[[:space:]]*//')
OWNER=$(grep -m1 "^负责人:" "$TASKS" | sed 's/^负责人:[[:space:]]*//')

AGENT="none"
REASON="No actionable task found"
ACTION="Wait"

case "$STATE" in
  pending)
    AGENT="$OWNER"
    REASON="任务处于 pending，负责人是 $OWNER"
    ACTION="切到 $OWNER window，认领并开始任务"
    ;;
  in-progress)
    AGENT="$OWNER"
    REASON="任务正在执行中"
    ACTION="查看 $OWNER 当前进度"
    ;;
  review)
    AGENT="reviewer"
    REASON="任务进入 review 状态"
    ACTION="切到 reviewer window，执行 review / qa"
    ;;
  blocked)
    AGENT="planner"
    REASON="任务被阻塞"
    ACTION="切到 planner window，处理 blocker 或重新分配任务"
    ;;
  done)
    AGENT="planner"
    REASON="任务已完成"
    ACTION="切到 planner window，确认归档"
    ;;
esac

cat > "$OUT" <<EOM
# Next Action

Agent: $AGENT

Task: ${TASK:-none}

Reason: $REASON

Action: $ACTION
EOM
