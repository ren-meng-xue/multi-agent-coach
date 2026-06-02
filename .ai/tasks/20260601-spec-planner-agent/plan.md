# Plan: spec-planner-agent

## Summary

创建 `.ai/agents/spec-planner.md`，一名专注写 spec 和 plan 的 agent，在 feature workflow 的 `spec` 和 `plan` step 被 supervisor 调出。

## Steps

### 1. 创建 agent 定义文件

写入 `.ai/agents/spec-planner.md`，严格遵循 Agent Schema（见 `.ai/agents/README.md`）：

- **Role**：专门负责写技术规格（spec.md）和执行计划（task.md + plan.md），被 supervisor 在 spec/plan step 时戴上面具
- **Responsibilities**：需求分析、技术方案拆解、spec 文档输出、plan 文档输出、workflow + depth 判定辅助
- **Workflow Responsibilities**：
  - `spec` step：调用 gstack `/spec` skill，写 spec.md
  - `plan` step：调用 superpowers `writing-plans` skill，写 task.md + plan.md
- **Role-specific Rules**：禁止写业务代码、禁止 review/testing
- **Handoff**：spec → plan → eng-review(by reviewer)

### 2. 更新 Agent Index

更新 `.ai/agents/README.md`：
- Agent List 表格加入 spec-planner
- Workflow Ownership 表格的 spec/plan step owner 标注 spec-planner
- Responsibility Boundary 和 Prohibited Actions 补充 spec-planner

### 3. 更新 workflow YAML

更新 `.ai/workflows/feature.yaml`：
- `spec` step：owner 从 `planner` 改为 `spec-planner`
- `plan` step：owner 从 `planner` 改为 `spec-planner`

## Deliverables

- `.ai/agents/spec-planner.md`
- `.ai/agents/README.md`（更新）
- `.ai/workflows/feature.yaml`（更新）

## Testing Strategy

- 人工 review agent 定义文件是否符合 Agent Schema
- 确认 workflow YAML 的 step owner 引用正确
- lint-protocol 跑一次确认无破坏
