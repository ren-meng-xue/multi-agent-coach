#!/usr/bin/env bash
set -e

TASKS="shared/current/tasks.md"
REVIEW="shared/current/review.md"
STATUS="shared/current/status.md"

STATE=$(grep -m1 "^状态:" "$TASKS" | sed 's/^状态:[[:space:]]*//')
TASK=$(grep -m1 "^### Task-" "$TASKS" | sed 's/^### //')

if [ "$STATE" != "review" ]; then
  exit 0
fi

set +e
./scripts/run-tests.sh
TEST_EXIT=$?
set -e

NOW=$(date "+%Y-%m-%d %H:%M")

if [ "$TEST_EXIT" -eq 0 ]; then
  DECISION="approved"
  RESULT="passing"
  NEW_STATE="done"
else
  DECISION="changes-requested"
  RESULT="failing"
  NEW_STATE="blocked"
fi

cat > "$REVIEW" <<EOM
# Review

## Current Review

状态: $DECISION
任务: $TASK
Reviewer: reviewer
最后更新: $NOW

## Summary

Automated review hook executed.

## Findings

- [ ] Test result: $RESULT

## Test Result

- command: ./scripts/run-tests.sh
- result: $RESULT

## Decision

$DECISION
EOM

perl -0pi -e "s/^状态:[[:space:]]*.*/状态: $NEW_STATE/m" "$TASKS"

cat > "$STATUS" <<EOM
# Status

最后更新: $NOW

review-hook executed.

Task: $TASK
Review decision: $DECISION
Test result: $RESULT
New task state: $NEW_STATE
EOM