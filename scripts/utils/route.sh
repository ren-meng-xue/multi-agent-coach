#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASKS="$ROOT/shared/current/tasks.md"
REVIEW="$ROOT/shared/current/review.md"
PARSE="$ROOT/scripts/utils/parse-task.sh"

if [ ! -f "$TASKS" ]; then
  exit 0
fi

# 提取所有 Task-NNN ID
task_ids=$(perl -ne 'print "$1\n" if /^### (Task-\d+)/' "$TASKS" || true)

for tid in $task_ids; do
  state=$("$PARSE" "$tid" state 2>/dev/null) || continue
  type=$("$PARSE" "$tid" type 2>/dev/null) || continue
  owner=$("$PARSE" "$tid" owner 2>/dev/null) || continue
  cancelled=$("$PARSE" "$tid" cancelled 2>/dev/null) || true

  # 跳过终态任务（done 且非 cancelled 需要 planner archive，done+cancelled 跳过）
  if [ "$state" = "done" ] && [ "$cancelled" != "true" ]; then
    echo "$tid planner dispatch (done→archive)"
    continue
  fi
  [ "$state" = "done" ] && [ "$cancelled" = "true" ] && continue

  # 检查 depends_on
  deps=$("$PARSE" "$tid" depends_on 2>/dev/null) || true
  skip=false
  if [ -n "$deps" ]; then
    IFS=',' read -ra DEP_ARR <<< "$deps"
    for dep in "${DEP_ARR[@]}"; do
      dep=$(echo "$dep" | xargs)
      dep_id=$(echo "$dep" | awk '{print $1}')
      dep_need=$(echo "$dep" | perl -ne 'print "$1" if /state>=(\w+)/' || echo "done")
      dep_state=$("$PARSE" "$dep_id" state 2>/dev/null) || dep_state="unknown"

      # 状态比较：done > review > in-progress > pending > blocked
      state_order="blocked pending in-progress review done"
      dep_pos=$(echo "$state_order" | tr ' ' '\n' | grep -n "^$dep_state$" | cut -d: -f1 || echo "0")
      need_pos=$(echo "$state_order" | tr ' ' '\n' | grep -n "^$dep_need$" | cut -d: -f1 || echo "0")
      if [ "$dep_pos" -lt "$need_pos" ] 2>/dev/null; then
        echo "$tid — waiting_on:$dep_id (current=$dep_state, need>=$dep_need)"
        skip=true
        break
      fi
    done
  fi
  [ "$skip" = "true" ] && continue

  # 路由表
  case "$state" in
    pending)
      echo "$tid $owner dispatch (pending→owner)"
      ;;
    in-progress)
      # owner 继续执行
      echo "$tid $owner dispatch (in-progress→owner)"
      ;;
    review)
      # 检查 review.md 的 decision
      decision=$(awk "/^### $tid/{found=1} found && /^\*\*Decision\*\*:/{print; exit}" "$REVIEW" 2>/dev/null | sed 's/.*Decision\*\*:[[:space:]]*//' || echo "")
      case "$decision" in
        "changes-requested")
          echo "$tid $owner dispatch (review→changes-requested→owner)"
          ;;
        "needs-discussion")
          echo "$tid planner dispatch (review→needs-discussion→planner)"
          ;;
        "approved")
          echo "$tid planner dispatch (review→approved→done)"
          ;;
        *)
          echo "$tid reviewer dispatch (review→reviewer)"
          ;;
      esac
      ;;
    blocked)
      echo "$tid planner dispatch (blocked→planner)"
      ;;
    *)
      echo "$tid — skipped:invalid_state ($state)"
      ;;
  esac
done
