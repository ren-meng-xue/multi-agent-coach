#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASK_ID="${1:-}"
STATUS="$ROOT/shared/current/status.md"
PARSE="$ROOT/scripts/utils/parse-task.sh"
RUN_TESTS="$ROOT/scripts/utils/run-tests.sh"

if [ -z "$TASK_ID" ]; then
  echo "Usage: review-hook.sh <task_id>" >&2
  exit 1
fi

# 校验 task 存在
state=$("$PARSE" "$TASK_ID" state 2>/dev/null) || {
  echo "[review-hook] $TASK_ID not found or parse error" >&2
  exit 1
}

type=$("$PARSE" "$TASK_ID" type 2>/dev/null) || type="feature"

# 跑测试
echo "[review-hook] Running tests for $TASK_ID..."
test_output=$("$RUN_TESTS" "$TASK_ID" 2>&1) || true
failed=$(echo "$test_output" | perl -ne 'if (/failed=(\d+)/) { print $1; exit; }')
failed=${failed:-0}
added=$(echo "$test_output" | perl -ne 'if (/added=(\d+)/) { print $1; exit; }')
added=${added:-0}

# 按 type 断言
case "$type" in
  refactor)
    if [ "$failed" -eq 0 ] && [ "$added" -eq 0 ]; then
      result="ok"
    else
      result="FAIL (refactor: expected 0 failed AND 0 added, got failed=$failed added=$added)"
    fi
    ;;
  test)
    if [ "$failed" -eq 0 ] && [ "$added" -ge 1 ]; then
      result="ok"
    else
      result="FAIL (test type: expected 0 failed AND >=1 added, got failed=$failed added=$added)"
    fi
    ;;
  release|rollback|hotfix)
    # 跳过 review，直接通过
    result="ok (skip review for $type)"
    ;;
  migration)
    if [ "$failed" -eq 0 ]; then
      result="ok"
    else
      result="FAIL (migration: expected 0 failed, got failed=$failed)"
    fi
    ;;
  *)
    if [ "$failed" -eq 0 ]; then
      result="ok"
    else
      result="FAIL (failed=$failed)"
    fi
    ;;
esac

# 追加到 status.md
echo "[$(date '+%Y-%m-%d %H:%M')] [review-hook] tests for $TASK_ID (type=$type): $failed failed, $added added -&gt; $result" >> "$STATUS"

# 去重：HEAD 未变则跳过 ownership/commit-prefix 检查
HEAD_HASH=$(git rev-parse HEAD 2>/dev/null || echo "")
LAST_CHECK_FILE="$ROOT/shared/current/.last-review-hook-${TASK_ID}"
LAST_HASH=$(cat "$LAST_CHECK_FILE" 2>/dev/null || echo "")
if [ "$HEAD_HASH" = "$LAST_HASH" ] && [ -n "$HEAD_HASH" ]; then
  exit 0
fi
echo "$HEAD_HASH" > "$LAST_CHECK_FILE"

# 权限检查 (C5)
OWNER=$("$PARSE" "$TASK_ID" owner 2>/dev/null)
CODEOWNERS="$ROOT/CODEOWNERS"
if [ -n "$OWNER" ] && [ -f "$CODEOWNERS" ]; then
  changed_files=$(git diff --name-only main...HEAD 2>/dev/null || true)
  for file in $changed_files; do
    # 查找匹配的 owner (最长路径匹配)
    matched_owners=$(perl -ane '
      BEGIN { $target = shift; $best_len = -1; $owners = ""; }
      if (/^(\S+)\s+(.+)$/) {
        $path = $1; $p_owners = $2;
        if ($target =~ /^\Q$path\E/) {
          if (length($path) > $best_len) {
            $best_len = length($path);
            $owners = $p_owners;
          }
        }
      }
      END { print $owners; }
    ' "$file" "$CODEOWNERS")

    if [ -n "$matched_owners" ]; then
      if ! echo "$matched_owners" | grep -qw "@$OWNER"; then
        echo "[$(date '+%Y-%m-%d %H:%M')] [review-hook] WARN ownership violation: $TASK_ID owned by $OWNER touched $file (per CODEOWNERS owner=$matched_owners)" >> "$STATUS"
      fi
    fi
  done
fi

# 检查 commit 前缀 (U6)
if git diff --name-only main...HEAD 2>/dev/null | grep -q .; then
  commits_without_prefix=$(git log --format="%h %s" main..HEAD 2>/dev/null | grep -v "\[$TASK_ID\]" || true)
  if [ -n "$commits_without_prefix" ]; then
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      echo "[$(date '+%Y-%m-%d %H:%M')] [review-hook] WARN commit prefix missing: $line" >> "$STATUS"
    done <<< "$commits_without_prefix"
  fi

  # 输出 commit 范围
  commit_hashes=$(git log --grep="\[$TASK_ID\]" --format="%H" main..HEAD 2>/dev/null || true)
  commit_count=$(echo "$commit_hashes" | grep -c . || echo "0")
  if [ "$commit_count" -gt 0 ]; then
    first=$(echo "$commit_hashes" | tail -1 | cut -c1-7)
    last=$(echo "$commit_hashes" | head -1 | cut -c1-7)
    echo "[$(date '+%Y-%m-%d %H:%M')] [review-hook] commits for $TASK_ID: ${first}..${last} (${commit_count} commits)" >> "$STATUS"
  fi
fi

exit 0
