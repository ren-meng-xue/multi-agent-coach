#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

TASKS="$ROOT/shared/current/tasks.md"
STATUS="$ROOT/shared/current/status.md"
REVIEW="$ROOT/shared/current/review.md"

STATE=$(grep -m1 "^状态:" "$TASKS" | sed 's/^状态:[[:space:]]*//')
TASK=$(grep -m1 "^### Task-" "$TASKS" | sed 's/^### //')

if [ "$STATE" != "done" ]; then
  exit 0
fi

TASK_ID=$(echo "$TASK" | cut -d':' -f1)
TASK_TITLE=$(echo "$TASK" | cut -d':' -f2- | xargs)

SLUG=$(echo "$TASK_TITLE" \
  | tr '[:upper:]' '[:lower:]' \
  | sed 's/调度/routing/g' \
  | sed 's/测试/test/g' \
  | sed 's/归档/archive/g' \
  | sed 's/审查/review/g' \
  | sed 's/状态/status/g' \
  | sed 's/[[:space:]]\+/-/g' \
  | sed 's/[^a-zA-Z0-9_-]/-/g' \
  | sed 's/-\+/-/g' \
  | sed 's/^-//;s/-$//')

if [ -z "$SLUG" ]; then
  SLUG="completed-task"
fi

ARCHIVE_DIR="$ROOT/shared/archive/${TASK_ID}-${SLUG}"

mkdir -p "$ARCHIVE_DIR"

cp "$TASKS" "$ARCHIVE_DIR/task.md"

if [ -f "$STATUS" ]; then
  cp "$STATUS" "$ARCHIVE_DIR/status.md"
fi

if [ -f "$REVIEW" ]; then
  cp "$REVIEW" "$ARCHIVE_DIR/review.md"
fi

cat > "$ARCHIVE_DIR/metadata.md" <<EOF
# $TASK_ID

Title: $TASK_TITLE

Task: $TASK

Archived At: $(date)

Final State: done
EOF

cat > "$TASKS" <<EOF
# Current Tasks

No active task.
EOF

cat > "$STATUS" <<EOF
# Status

Archive completed.

Task:
$TASK

Archive:
$ARCHIVE_DIR

Archived at:
$(date)
EOF

echo "Archived: $TASK"
echo "Location: $ARCHIVE_DIR"