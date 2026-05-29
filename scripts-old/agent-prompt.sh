#!/usr/bin/env bash

AGENT="$1"

CONTEXT="shared/current/agent-context.md"
OUT="shared/current/agent-prompt.md"

if [ -z "$AGENT" ]; then
  echo "Usage: ./scripts/agent-prompt.sh <agent>"
  exit 1
fi

if [ ! -f "$CONTEXT" ]; then
  echo "Missing context file: $CONTEXT"
  echo "Run: ./scripts/agent-context.sh $AGENT"
  exit 1
fi

{
  echo "# Agent Prompt"
  echo
  echo "You are the $AGENT agent in this Multi-Agent Cockpit."
  echo
  echo "Please read the full context file first:"
  echo
  echo "\`\`\`txt"
  echo "$CONTEXT"
  echo "\`\`\`"
  echo
  echo "Your task:"
  echo
  echo "1. Read CLAUDE.md."
  echo "2. Read your role file: agents/$AGENT.md."
  echo "3. Read shared/current/agent-context.md."
  echo "4. Follow the current task state, owner, and workflow rules."
  echo "5. Only modify files allowed by your role and file ownership rules."
  echo "6. Update shared/current/status.md with what you did."
  echo "7. If your work is complete, move the task to the next valid state."
  echo
  echo "Important:"
  echo
  echo "- Do not skip required context."
  echo "- Do not take over another agent's responsibility."
  echo "- Do not mark a task done unless you are planner."
  echo "- If blocked, update the task state to blocked and explain why."
} > "$OUT"

echo "Generated: $OUT"