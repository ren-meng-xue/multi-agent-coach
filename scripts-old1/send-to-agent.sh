#!/usr/bin/env bash
set -euo pipefail

AGENT="${1:-}"
PROMPT_FILE="${2:-}"

if [ -z "$AGENT" ] || [ -z "$PROMPT_FILE" ]; then
  echo "Usage: send-to-agent.sh <agent> <prompt_file>" >&2
  exit 1
fi

case "$AGENT" in
  planner|backend|frontend|reviewer) ;;
  *)
    echo "Invalid agent: $AGENT (must be planner|backend|frontend|reviewer)" >&2
    exit 1
    ;;
esac

if [ ! -f "$PROMPT_FILE" ]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

WINDOW="multi-agent:$AGENT"

# 检查 window 是否存在
if ! tmux list-windows -t multi-agent 2>/dev/null | grep -q "$AGENT"; then
  echo "[send-to-agent] window $WINDOW not found" >&2
  exit 1
fi

# 检查 agent 是否 idle（末行是否为 prompt 符号）
last_line=$(tmux capture-pane -p -t "$WINDOW" 2>/dev/null | tail -1 || echo "")
if echo "$last_line" | grep -qE '[>$#]'; then
  # idle，发送唤醒指令
  tmux send-keys -t "$WINDOW" "$(cat "$PROMPT_FILE")" Enter
  echo "[send-to-agent] sent wakeup to $AGENT"
else
  echo "[send-to-agent] $AGENT busy, skipping"
  exit 2
fi
