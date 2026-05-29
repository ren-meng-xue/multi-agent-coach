#!/usr/bin/env bash

AGENT="$1"
NEXT_ACTION="shared/current/next-action.md"

while true; do
  CURRENT=$(grep -m1 "^Agent:" "$NEXT_ACTION" | sed 's/^Agent:[[:space:]]*//')

  clear
  echo "Agent: $AGENT"
  echo "Next:  $CURRENT"
  echo

  if [ "$CURRENT" = "$AGENT" ]; then
    ./scripts/agent-context.sh "$AGENT"
    ./scripts/agent-prompt.sh "$AGENT"

    echo ">>> YOUR TURN <<<"
    echo
    echo "Context generated:"
    echo "shared/current/agent-context.md"
    echo
    echo "Prompt generated:"
    echo "shared/current/agent-prompt.md"
  else
    echo "Waiting..."
  fi

  sleep 2
done