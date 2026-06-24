#!/bin/bash
# 收尾钩子：Stop → lint + unit tests，最多阻止 3 次，之后放行
set -euo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-.}"
retry_file="$project_dir/.claude/.stop-gate-retry"
max_retries=3

# 读取当前重试计数，超过 2 小时自动重置
retry_count=0
if [ -f "$retry_file" ]; then
  now=$(date +%s)
  file_mtime=$(stat -f %m "$retry_file" 2>/dev/null || stat -c %Y "$retry_file" 2>/dev/null || echo 0)
  if [ "$((now - file_mtime))" -gt 7200 ]; then
    rm -f "$retry_file"
  else
    retry_count=$(cat "$retry_file" 2>/dev/null || echo 0)
  fi
fi

failures=""

# Backend lint
if ! "$project_dir/.venv/bin/python" -m ruff check "$project_dir/backend" --output-format=concise 2>/dev/null; then
  failures="${failures}
  - ruff lint 未通过"
fi

# Backend unit tests
if [ -d "$project_dir/backend/tests/unit" ]; then
  if ! "$project_dir/.venv/bin/python" -m pytest "$project_dir/backend/tests/unit/" -x -q --tb=line 2>/dev/null; then
    failures="${failures}
  - 后端单元测试未通过"
  fi
fi

# Frontend type check
if [ -f "$project_dir/frontend/tsconfig.json" ]; then
  if ! npx --prefix "$project_dir/frontend" tsc --noEmit 2>/dev/null; then
    failures="${failures}
  - tsc 类型检查未通过"
  fi
fi

# 全部通过 → 清除计数，放行
if [ -z "$failures" ]; then
  rm -f "$retry_file"
  exit 0
fi

# 超过最大重试次数 → 放行（不再阻止）
if [ "$retry_count" -ge "$max_retries" ]; then
  rm -f "$retry_file"
  exit 0
fi

# 阻止并递增计数
retry_count=$((retry_count + 1))
echo "$retry_count" > "$retry_file"
printf '{"continue":false,"stopReason":"[%s/%s] 收尾检查未通过，请修复:%s"}' "$retry_count" "$max_retries" "$failures"
