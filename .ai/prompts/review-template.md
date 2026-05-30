# Review: <Semantic-Task-Name>

## 1. 结论 (Verdict)
> 必须是以下两者之一，禁止模棱两可的表达：
> **[ APPROVED ]** - 代码符合要求，可以进入测试阶段。
> **[ CHANGES_REQUESTED ]** - 存在必须修复的问题，退回给执行者。

## 2. 计划对齐检查 (Alignment Check)
*   [ ] 代码实现是否完全覆盖了 `task.md` 中的目标？
*   [ ] 代码修改是否严格限制在 `plan.md` 划定的范围内？（指出任何超出范围的修改）

## 3. 详细反馈 (Detailed Findings)

### 阻碍性问题 (Blockers - 如果 Verdict 是 APPROVED，此项可写无)
> 列出导致退回的严重问题，并说明如何修复。
*   ...

### 优化建议 (Minor Suggestions)
> 列出不影响核心功能，但建议优化的点（例如：代码风格、命名规范等）。
*   ...

## 4. 后续动作 (Next Actions)
*   (如果 Approved)：交由 Tester 进行最终验收。
*   (如果 Changes Requested)：交还给 Backend/Frontend，请重点关注上述“阻碍性问题”并修复。