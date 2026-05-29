#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAST_DISPATCH="$ROOT/shared/current/.last-dispatched"
HEALTH="$ROOT/shared/current/.cockpit-health.md"
PIDFILE="$ROOT/shared/current/.cockpit.pid"
ROUTE="$ROOT/scripts/utils/route.sh"
SEND="$ROOT/scripts/send-to-agent.sh"
REVIEW_HOOK="$ROOT/scripts/hooks/review-hook.sh"
GENERATOR="$ROOT/scripts/planner-task-generator.sh"
INPUT="$ROOT/shared/current/input.md"
PARSE="$ROOT/scripts/utils/parse-task.sh"

# PID 锁
if [ -f "$PIDFILE" ]; then
  old_pid=$(cat "$PIDFILE")
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "[control-plane] already running (PID $old_pid)" >&2
    exit 1
  fi
fi
echo $$ > "$PIDFILE"

# 退出清理
cleanup() {
  rm -f "$PIDFILE"
  echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] stopped" >> "$ROOT/shared/current/status.md"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] started" >> "$ROOT/shared/current/status.md"

# status.md 滚动归档 (C3)
STATUS="$ROOT/shared/current/status.md"
if [ -f "$STATUS" ]; then
  STATUS_LINES=$(wc -l < "$STATUS")
  if [ "$STATUS_LINES" -gt 500 ]; then
    STATUS_ARCHIVE="$ROOT/shared/archive/status-log-$(date +%Y-%m-%d).md"
    cp "$STATUS" "$STATUS_ARCHIVE"
    echo "# Status Log" > "$STATUS"
    echo "" >> "$STATUS"
    echo "<!-- rolled over from $STATUS_ARCHIVE -->" >> "$STATUS"
    echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] status.md rolled over to $STATUS_ARCHIVE" >> "$STATUS"
  fi
fi

# 初始化 .last-dispatched 和 health 文件
[ -f "$LAST_DISPATCH" ] || echo '{}' > "$LAST_DISPATCH"
[ -f "$HEALTH" ] || echo "# Cockpit Health" > "$HEALTH"

# .last-dispatched 损坏检测与自愈
validate_json() {
  python3 -c "import json, sys; json.load(open(sys.argv[1]))" "$1" 2>/dev/null
}
if [ -s "$LAST_DISPATCH" ] && ! validate_json "$LAST_DISPATCH"; then
  ts=$(date +%s)
  cp "$LAST_DISPATCH" "${LAST_DISPATCH}.broken-${ts}"
  echo '{}' > "$LAST_DISPATCH"
  echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] WARN .last-dispatched corrupted, backed up to .last-dispatched.broken-${ts}" >> "$HEALTH"
fi

# JSON 读取辅助（纯 bash，不依赖 jq）
read_json_field() {
  local key="$1"
  local file="$2"
  perl -ne "print \"\$1\" if /\"$key\":\"([^\"]*)\"/" "$file" 2>/dev/null | head -1 || echo ""
}

# 死锁检测 (Bash 3.2 兼容：使用变量名动态拼接)
get_stall_count() {
  local tid=$(echo "$1" | tr -cd '[:alnum:]')
  eval "echo \${stall_count_$tid:-0}"
}
set_stall_count() {
  local tid=$(echo "$1" | tr -cd '[:alnum:]')
  eval "stall_count_$tid=$2"
}

# 首次启动 / 重连：检测 agent window 是否已 bootstrap
bootstrap_if_needed() {
  for agent in planner backend frontend reviewer; do
    window="multi-agent:$agent"
    if tmux list-windows -t multi-agent 2>/dev/null | grep -q "$agent"; then
      last_screen=$(tmux capture-pane -p -t "$window" 2>/dev/null | tail -30 || echo "")
      if ! echo "$last_screen" | grep -q "我是.*角色"; then
        bootstrap_file="$ROOT/scripts/prompts/bootstrap-${agent}.txt"
        if [ -f "$bootstrap_file" ]; then
          "$SEND" "$agent" "$bootstrap_file" 2>/dev/null || true
          echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] bootstrap sent to $agent" >> "$ROOT/shared/current/status.md"
        fi
      fi
    else
      echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] WARN window $agent not found" >> "$HEALTH"
    fi
  done
}

bootstrap_if_needed

# 初始化 input.md
[ -f "$INPUT" ] || touch "$INPUT"

while true; do
  # 检测人工输入 → 生成任务
  [ -s "$INPUT" ] && "$GENERATOR"

  # 备份旧 dispatch 状态
  old_dispatch=$(cat "$LAST_DISPATCH" 2>/dev/null || echo '{}')

  # 新 dispatch 状态
  new_dispatch='{'

  # 运行路由
  route_output=$("$ROUTE" 2>&1) || true

  # 构建 next-action.md
  cat > "$ROOT/shared/current/next-action.md" <<NEXTEOF
# Next Action

## Active dispatches
NEXTEOF

  # 按 agent 聚合 (Bash 3.2 兼容)
  planner_next=""
  planner_queue=""
  backend_next=""
  backend_queue=""
  frontend_next=""
  frontend_queue=""
  reviewer_next=""
  reviewer_queue=""

  while IFS= read -r line; do
    [ -z "$line" ] && continue

    tid=$(echo "$line" | awk '{print $1}')
    agent=$(echo "$line" | awk '{print $2}')
    reason=$(echo "$line" | awk '{print $3" "$4" "$5" "$6" "$7}' | xargs)

    # 跳过 waiting_on 和 skipped
    if echo "$line" | grep -qE '(waiting_on|skipped)'; then
      echo "### $tid" >> "$ROOT/shared/current/next-action.md"
      echo "Agent: --" >> "$ROOT/shared/current/next-action.md"
      echo "Reason: $reason" >> "$ROOT/shared/current/next-action.md"
      echo "" >> "$ROOT/shared/current/next-action.md"

      # 报警到 health
      if echo "$reason" | grep -q "invalid_state"; then
        echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] WARN $tid has $reason" >> "$HEALTH"
      fi
      if echo "$reason" | grep -q "circular_dependency"; then
        echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] WARN circular dependency detected: $reason" >> "$HEALTH"
      fi

      continue
    fi

    echo "### $tid" >> "$ROOT/shared/current/next-action.md"
    echo "Agent: $agent" >> "$ROOT/shared/current/next-action.md"
    echo "Reason: $reason" >> "$ROOT/shared/current/next-action.md"
    echo "" >> "$ROOT/shared/current/next-action.md"

    # 聚合 agent queue (C11: 移动到去重之前，确保 next-action.md 完整)
    task_type=$("$PARSE" "$tid" type 2>/dev/null || echo "feature")
    task_priority=$("$PARSE" "$tid" priority 2>/dev/null || echo "normal")
    
    item="$tid ($task_type, priority=$task_priority)"
    case "$agent" in
      planner)
        if [ -z "$planner_next" ]; then planner_next="$item"; else planner_queue="$planner_queue $item"; fi
        ;;
      backend)
        if [ -z "$backend_next" ]; then backend_next="$item"; else backend_queue="$backend_queue $item"; fi
        ;;
      frontend)
        if [ -z "$frontend_next" ]; then frontend_next="$item"; else frontend_queue="$frontend_queue $item"; fi
        ;;
      reviewer)
        if [ -z "$reviewer_next" ]; then reviewer_next="$item"; else reviewer_queue="$reviewer_queue $item"; fi
        ;;
    esac

    # 去重检查 .last-dispatched
    last_state=$(read_json_field "$tid" "$LAST_DISPATCH" || echo "")
    current_state=$("$PARSE" "$tid" state 2>/dev/null || echo "unknown")

    dispatch_key="${tid}:${current_state}:${agent}"

    # 更新 new_dispatch
    new_dispatch+="\"$tid\":\"$current_state:$agent\","

    if [ "$last_state" = "$current_state:$agent" ]; then
      # 去重：上一轮已派过同一个 (task, state, agent)
      # 检查死锁
      cnt=$(get_stall_count "$tid")
      cnt=$((cnt + 1))
      set_stall_count "$tid" "$cnt"
      if [ "$cnt" -ge 10 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] WARN stall detected: $tid $current_state -> $agent ($cnt cycles)" >> "$HEALTH"
      fi
      continue
    fi

    # 重置停滞计数
    set_stall_count "$tid" 0

    # state=review: 先跑 review-hook
    if [ "$current_state" = "review" ]; then
      "$REVIEW_HOOK" "$tid" 2>/dev/null || true
    fi

    # 发送唤醒
    prompt_file="$ROOT/scripts/prompts/wakeup.txt"
    "$SEND" "$agent" "$prompt_file" 2>/dev/null || {
      echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] WARN failed to wake $agent for $tid" >> "$HEALTH"
    }
  done <<< "$route_output"

  new_dispatch="${new_dispatch%,}}"
  echo "$new_dispatch" > "$LAST_DISPATCH"

  # 追加 Agent queues 到 next-action.md
  cat >> "$ROOT/shared/current/next-action.md" <<NEXTEOF
## Agent queues
NEXTEOF

  for agent in planner backend frontend reviewer; do
    eval "next_val=\$${agent}_next"
    eval "queue_val=\$${agent}_queue"
    if [ -n "$next_val" ]; then
      echo "### $agent" >> "$ROOT/shared/current/next-action.md"
      echo "Next: $next_val" >> "$ROOT/shared/current/next-action.md"
      [ -n "$queue_val" ] && echo "Queue:$queue_val" >> "$ROOT/shared/current/next-action.md"
      echo "" >> "$ROOT/shared/current/next-action.md"
    fi
  done

  # 追加 Dependency graph 到 next-action.md
  cat >> "$ROOT/shared/current/next-action.md" <<NEXTEOF
## Dependency graph
NEXTEOF
  echo "$route_output" | grep -v 'dispatch\|skipped' >> "$ROOT/shared/current/next-action.md" 2>/dev/null || echo "(no dependencies)" >> "$ROOT/shared/current/next-action.md"

  unset agent_next
  unset agent_queue

  sleep 2
done
