#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAST_DISPATCH="$ROOT/shared/current/.last-dispatched"
HEALTH="$ROOT/shared/current/.cockpit-health.md"
PIDFILE="$ROOT/shared/current/.cockpit.pid"
ROUTE="$ROOT/scripts/utils/route.sh"
SEND="$ROOT/scripts/send-to-agent.sh"
REVIEW_HOOK="$ROOT/scripts/hooks/review-hook.sh"
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

# 初始化 .last-dispatched 和 health 文件
[ -f "$LAST_DISPATCH" ] || echo '{}' > "$LAST_DISPATCH"
[ -f "$HEALTH" ] || echo "# Cockpit Health" > "$HEALTH"

# JSON 读取辅助（纯 bash，不依赖 jq）
read_json_field() {
  local key="$1"
  local file="$2"
  perl -ne "print \"\$1\" if /\"$key\":\"([^\"]*)\"/" "$file" 2>/dev/null | head -1 || echo ""
}

# 死锁检测
declare -A stall_count

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
      echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] ⚠ window $agent not found" >> "$HEALTH"
    fi
  done
}

bootstrap_if_needed

while true; do
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

  # 按 agent 聚合
  declare -A agent_next
  declare -A agent_queue

  while IFS= read -r line; do
    [ -z "$line" ] && continue

    tid=$(echo "$line" | awk '{print $1}')
    agent=$(echo "$line" | awk '{print $2}')
    reason=$(echo "$line" | awk '{print $3" "$4" "$5" "$6" "$7}' | xargs)

    # 跳过 waiting_on 和 skipped
    if echo "$line" | grep -qE '(waiting_on|skipped)'; then
      echo "### $tid" >> "$ROOT/shared/current/next-action.md"
      echo "Agent: —" >> "$ROOT/shared/current/next-action.md"
      echo "Reason: $reason" >> "$ROOT/shared/current/next-action.md"
      echo "" >> "$ROOT/shared/current/next-action.md"
      continue
    fi

    echo "### $tid" >> "$ROOT/shared/current/next-action.md"
    echo "Agent: $agent" >> "$ROOT/shared/current/next-action.md"
    echo "Reason: $reason" >> "$ROOT/shared/current/next-action.md"
    echo "" >> "$ROOT/shared/current/next-action.md"

    # 去重检查 .last-dispatched
    last_state=$(read_json_field "$tid" "$LAST_DISPATCH" || echo "")
    current_state=$("$PARSE" "$tid" state 2>/dev/null || echo "unknown")

    dispatch_key="${tid}:${current_state}:${agent}"

    # 更新 new_dispatch
    new_dispatch+="\"$tid\":\"$current_state:$agent\","

    if [ "$last_state" = "$current_state:$agent" ]; then
      # 去重：上一轮已派过同一个 (task, state, agent)
      # 检查死锁
      stall_count["$tid"]=$((${stall_count["$tid"]:-0} + 1))
      if [ ${stall_count["$tid"]} -ge 10 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] ⚠ stall detected: $tid $current_state→$agent (${stall_count["$tid"]} cycles)" >> "$HEALTH"
      fi
      continue
    fi

    # 重置停滞计数
    stall_count["$tid"]=0

    # state=review: 先跑 review-hook
    if [ "$current_state" = "review" ]; then
      "$REVIEW_HOOK" "$tid" 2>/dev/null || true
    fi

    # 发送唤醒
    prompt_file="$ROOT/scripts/prompts/wakeup.txt"
    "$SEND" "$agent" "$prompt_file" 2>/dev/null || {
      echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] ⚠ failed to wake $agent for $tid" >> "$HEALTH"
    }

    # 聚合 agent queue
    task_type=$("$PARSE" "$tid" type 2>/dev/null || echo "feature")
    task_priority=$("$PARSE" "$tid" priority 2>/dev/null || echo "normal")
    if [ -z "${agent_next[$agent]:-}" ]; then
      agent_next[$agent]="$tid ($task_type, priority=$task_priority)"
    else
      agent_queue[$agent]="${agent_queue[$agent]:-} $tid ($task_type, priority=$task_priority)"
    fi
  done <<< "$route_output"

  new_dispatch="${new_dispatch%,}}"
  echo "$new_dispatch" > "$LAST_DISPATCH"

  # 追加 Agent queues 到 next-action.md
  cat >> "$ROOT/shared/current/next-action.md" <<NEXTEOF
## Agent queues
NEXTEOF

  for agent in planner backend frontend reviewer; do
    if [ -n "${agent_next[$agent]:-}" ]; then
      echo "### $agent" >> "$ROOT/shared/current/next-action.md"
      echo "Next: ${agent_next[$agent]}" >> "$ROOT/shared/current/next-action.md"
      [ -n "${agent_queue[$agent]:-}" ] && echo "Queue:${agent_queue[$agent]}" >> "$ROOT/shared/current/next-action.md"
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
