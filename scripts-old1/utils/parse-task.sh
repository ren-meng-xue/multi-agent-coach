#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASKS="$ROOT/shared/current/tasks.md"

TASK_ID="${1:-}"
FIELD="${2:-}"

if [ -z "$TASK_ID" ]; then
  echo "Usage: parse-task.sh <task_id> [field]" >&2
  exit 1
fi

if [ ! -f "$TASKS" ]; then
  echo '{"error":"tasks.md not found"}' >&2
  exit 1
fi

# 提取 ### Task-NNN ... 到下一个 ### 或 EOF
BLOCK=$(awk "/^### $TASK_ID[ :]/{found=1} found{print} /^### /&&found&&!/^### $TASK_ID[ :]/{exit}" "$TASKS")

if [ -z "$BLOCK" ]; then
  echo "{\"error\":\"$TASK_ID not found\"}" >&2
  exit 1
fi

# 解析字段
get_field() {
  local f="$1"
  echo "$BLOCK" | grep -m1 "^${f}:" | sed "s/^${f}:[[:space:]]*//" || echo ""
}

STATE=$(get_field "状态")
TYPE=$(get_field "类型")
OWNER=$(get_field "负责人")
DEPENDS_ON=$(get_field "depends_on")
PRIORITY=$(get_field "priority")
CANCELLED=$(get_field "cancelled")
CREATED_AT=$(get_field "创建时间")

# 必填字段检查
if [ -z "$STATE" ] || [ -z "$TYPE" ] || [ -z "$OWNER" ]; then
  missing=""
  [ -z "$STATE" ] && missing="state"
  [ -z "$TYPE" ] && missing="type"
  [ -z "$OWNER" ] && missing="owner"
  echo "{\"error\":\"missing required field: $missing\",\"task_id\":\"$TASK_ID\"}" >&2
  exit 2
fi

# 合法值校验
VALID_STATES="pending in-progress review blocked done"
VALID_TYPES="feature refactor bugfix test trivial investigate spike release rollback migration hotfix"

if ! echo "$VALID_STATES" | grep -qw "$STATE"; then
  echo "{\"error\":\"invalid state: $STATE\",\"task_id\":\"$TASK_ID\"}" >&2
  exit 2
fi

if ! echo "$VALID_TYPES" | grep -qw "$TYPE"; then
  echo "{\"error\":\"invalid type: $TYPE\",\"task_id\":\"$TASK_ID\"}" >&2
  exit 2
fi

PRIORITY="${PRIORITY:-normal}"

if [ -n "$FIELD" ]; then
  case "$FIELD" in
    state) echo "$STATE" ;;
    type) echo "$TYPE" ;;
    owner) echo "$OWNER" ;;
    depends_on) echo "$DEPENDS_ON" ;;
    priority) echo "$PRIORITY" ;;
    cancelled) echo "$CANCELLED" ;;
    created_at) echo "$CREATED_AT" ;;
    *)
      echo "Unknown field: $FIELD" >&2
      exit 1
      ;;
  esac
else
  # 输出 JSON
  cat <<JSONEOF
{"task_id":"$TASK_ID","state":"$STATE","type":"$TYPE","owner":"$OWNER","depends_on":"$DEPENDS_ON","priority":"$PRIORITY","cancelled":"$CANCELLED","created_at":"$CREATED_AT"}
JSONEOF
fi
