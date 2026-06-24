#!/bin/bash
# 质量钩子：PostToolUse + Write/Edit → 自动格式化
set -euo pipefail

file_path=$(jq -r '.tool_input.file_path // ""' 2>/dev/null || true)
[ -z "$file_path" ] && exit 0

project_dir="${CLAUDE_PROJECT_DIR:-.}"
cd "$project_dir"

# Python → ruff
if echo "$file_path" | grep -qE '\.py$'; then
  .venv/bin/python -m ruff format "$file_path" 2>/dev/null || true
  .venv/bin/python -m ruff check --fix "$file_path" 2>/dev/null || true
  exit 0
fi

# Frontend → prettier
if echo "$file_path" | grep -qE '\.(tsx?|jsx?|css|json|md)$'; then
  npx prettier --write "$file_path" 2>/dev/null || true
  exit 0
fi
