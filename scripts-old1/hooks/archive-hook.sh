#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASK_ID="${1:-}"

if [ -z "$TASK_ID" ]; then
  echo "Usage: archive-hook.sh <task_id>" >&2
  exit 1
fi

TASKS="$ROOT/shared/current/tasks.md"
STATUS="$ROOT/shared/current/status.md"
REVIEW="$ROOT/shared/current/review.md"
NEXT_ACTION="$ROOT/shared/current/next-action.md"
PARSE="$ROOT/scripts/utils/parse-task.sh"

# 校验 task 存在且 state=done
state=$("$PARSE" "$TASK_ID" state 2>/dev/null) || {
  echo "[archive-hook] $TASK_ID not found" >&2
  exit 1
}

if [ "$state" != "done" ]; then
  echo "[archive-hook] $TASK_ID state=$state, must be done" >&2
  exit 2
fi

# 提取 task slug（从标题取）
task_title=$(grep -m1 "^### $TASK_ID:" "$TASKS" | sed "s/^### $TASK_ID:[[:space:]]*//" || echo "$TASK_ID")
slug=$(echo "$task_title" | tr ' ' '-' | tr -cd '[:alnum:]-_' | cut -c1-50)

ARCHIVE_DIR="$ROOT/shared/archive/${TASK_ID}-${slug}"
TMP_DIR="${ARCHIVE_DIR}.tmp"

# 检查是否已归档
if [ -d "$ARCHIVE_DIR" ]; then
  echo "[archive-hook] $TASK_ID already archived at $ARCHIVE_DIR" >&2
  exit 3
fi

# 原子化：先写到 .tmp
rm -rf "$TMP_DIR" 2>/dev/null || true
mkdir -p "$TMP_DIR"

# 截取 tasks.md 中该 Task 段
awk "/^### $TASK_ID[ :]/{found=1} found{print} /^### /&&found&&!/^### $TASK_ID[ :]/{exit}" "$TASKS" > "$TMP_DIR/task.md"

# 过滤 status.md 中包含该 Task 的行
grep "$TASK_ID" "$STATUS" > "$TMP_DIR/status.md" 2>/dev/null || touch "$TMP_DIR/status.md"

# 截取 review.md 中该 Task 段
awk "/^### $TASK_ID[ :]/{found=1} found{print} /^### /&&found&&!/^### $TASK_ID[ :]/{exit}" "$REVIEW" > "$TMP_DIR/review.md" 2>/dev/null || touch "$TMP_DIR/review.md"

# 列出引用的 decisions
perl -ne 'print "$1\n" while /decisions\/([^ ]+)/g' "$TMP_DIR/status.md" 2>/dev/null | sort -u > "$TMP_DIR/decisions.txt" || touch "$TMP_DIR/decisions.txt"

# 原子化提交：mv .tmp → 正式目录
mv "$TMP_DIR" "$ARCHIVE_DIR"

# 清理 current/ 文件
# tasks.md: 删除该 Task 段
awk "/^### $TASK_ID[ :]/{found=1; next} /^### /&&found{found=0} !found{print}" "$TASKS" > "${TASKS}.tmp" && mv "${TASKS}.tmp" "$TASKS"

# review.md: 删除该 Task 段
awk "/^### $TASK_ID[ :]/{found=1; next} /^### /&&found{found=0} !found{print}" "$REVIEW" > "${REVIEW}.tmp" && mv "${REVIEW}.tmp" "$REVIEW"

# next-action.md: 删除该 Task 段
awk "/^### $TASK_ID[ :]/{found=1; next} /^### /&&found{found=0} !found{print}" "$NEXT_ACTION" > "${NEXT_ACTION}.tmp" && mv "${NEXT_ACTION}.tmp" "$NEXT_ACTION"

# status.md 保留全文（不删），超 500 行时整体归档
STATUS_LINES=$(wc -l < "$STATUS")
if [ "$STATUS_LINES" -gt 500 ]; then
  STATUS_ARCHIVE="$ROOT/shared/archive/status-log-$(date +%Y-%m-%d).md"
  cp "$STATUS" "$STATUS_ARCHIVE"
  echo "# Status Log" > "$STATUS"
  echo "" >> "$STATUS"
  echo "<!-- rolled over from $STATUS_ARCHIVE -->" >> "$STATUS"
fi

echo "[$(date '+%Y-%m-%d %H:%M')] [archive-hook] Archived $TASK_ID → $ARCHIVE_DIR" >> "$STATUS"
echo "[archive-hook] Archived $TASK_ID → $ARCHIVE_DIR"
