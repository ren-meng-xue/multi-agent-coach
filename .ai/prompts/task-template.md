# Task: <Semantic-Task-Name>

## 1. 背景与目的 (Background & Goal)
*   **背景**：为什么要做这个任务？（例如：用户反馈了某个 Bug，或者需要支持某个新业务）。
*   **目标**：本次任务期望达成的最终结果是什么？

## 2. 需求范围 (Scope)
*   **In Scope (包含)**：
    *   明确要做的功能点 1。
    *   明确要做的功能点 2。
*   **Out of Scope (不包含)**：
    *   明确说明**不要做**的事情，防止过度设计或偏离主题。

## 3. 验收标准 (Acceptance Criteria)
> **给 Tester 的话**：请在测试阶段逐一核对以下条件，全部满足方可将状态置为 DONE。

- [ ] 条件 1：(例如：当输入 X 时，UI 应该显示 Y)。
- [ ] 条件 2：(例如：相关状态必须在 status.json 中正确更新)。
- [ ] 条件 3：(例如：没有引入新的编译警告或错误)。

## 4. 工作流关联 (Workflow)
*   **使用的流程剧本**：`.ai/workflows/<workflow-name>.yaml` (例如：feature.yaml, bugfix.yaml)