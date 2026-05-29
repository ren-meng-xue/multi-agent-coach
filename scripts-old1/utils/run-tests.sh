#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASK_ID="${1:-}"

if [ -z "$TASK_ID" ]; then
  echo "Usage: run-tests.sh <task_id>" >&2
  exit 1
fi

cd "$ROOT"

failed=0
added=0

# 后端测试
if [ -d backend ]; then
  cd backend
  if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
    # 跑 pytest，捕获尾行统计
    pytest_output=$(pytest -q --tb=no 2>&1) || true
    failed=$(echo "$pytest_output" | perl -ne 'if (/(\d+) failed/) { print $1; exit; }')
    failed=${failed:-0}
    cd "$ROOT"
  else
    echo "venv not found in backend/" >&2
    exit 1
  fi
fi

# 前端测试（骨架）
if git diff --name-only main...HEAD 2>/dev/null | grep -q '^html/'; then
  # 当前项目无前端测试栈，跳过
  :
fi

# 新增测试文件计数
added=$(git diff --name-only --diff-filter=A main...HEAD 2>/dev/null | grep -cE '(backend/tests/|tests/)' || echo "0")

echo "failed=$failed added=$added"
