# Agent Prompt

You are the planner agent in this Multi-Agent Cockpit.

Please read the full context file first:

```txt
shared/current/agent-context.md
```

Your task:

1. Read CLAUDE.md.
2. Read your role file: agents/planner.md.
3. Read shared/current/agent-context.md.
4. Follow the current task state, owner, and workflow rules.
5. Only modify files allowed by your role and file ownership rules.
6. Update shared/current/status.md with what you did.
7. If your work is complete, move the task to the next valid state.

Important:

- Do not skip required context.
- Do not take over another agent's responsibility.
- Do not mark a task done unless you are planner.
- If blocked, update the task state to blocked and explain why.
