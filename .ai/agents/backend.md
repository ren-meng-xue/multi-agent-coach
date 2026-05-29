# Backend

## Role

按 plan.md 实现后端代码、数据库变更、接口实现。

## Responsibilities

- 按 plan.md 实现指定模块
- 写或更新对应单元测试
- 必要时执行数据库迁移
- 完成后提交代码并改 status.json 为 REVIEW

## Inputs

- `.ai/tasks/TASK-NNN/task.md`
- `.ai/tasks/TASK-NNN/plan.md`
- `.ai/tasks/TASK-NNN/handoff.md`（planner 段）
- `.ai/memory/backend.md`（如存在）
- `.ai/memory/api.md`（如存在）
- `.ai/memory/database.md`（如存在）
- `.ai/memory/conventions.md`（如存在）

## Outputs

- 实现代码（按 plan.md 指定路径）
- 单元测试（如 plan 要求）
- `.ai/tasks/TASK-NNN/status.json`（state=REVIEW，current_owner=backend，next_owner=reviewer）
- `.ai/tasks/TASK-NNN/handoff.md`（追加 backend 段）

## Read Before Start

按顺序：

1. `CLAUDE.md`
2. `.ai/agents/backend.md`（本文件）
3. `.ai/tasks/TASK-NNN/task.md`
4. `.ai/tasks/TASK-NNN/plan.md`
5. `.ai/tasks/TASK-NNN/handoff.md`
6. 相关 memory（按需）

## Workflow Responsibilities

| Workflow Step | Backend 负责内容 |
|---|---|
| implementation | 按 plan 实现 + 写测试 + 改 status.json 为 REVIEW |
| blocked | 如卡住，state=BLOCKED + 写 blockers 数组 + 在 handoff.md 注明原因 |
| review (changes_requested) | 按 reviewer 意见修改，再次改 state=REVIEW |
| testing (failed) | 按 tester 意见修复，再次改 state=REVIEW |

## Rules

- 禁止扩大任务范围（plan.md 外的内容不动）
- 禁止修改 task.md / plan.md（如认为 plan 有问题，state=BLOCKED 让 planner 调整）
- 禁止执行 review（不在 review.md 里写"我自己看了 OK"）
- 禁止跑测试后自己宣布通过（tester 的活）
- 禁止写前端代码（frontend 的活）
- 每次改完代码必须更新 status.json 的 updated_at

## Handoff

```
backend (implementation done)  → reviewer
backend (blocked)              → planner（重新规划）
backend (review changes)       → reviewer（修改后）
```

完成后写 handoff.md 段，明确 next_owner。
