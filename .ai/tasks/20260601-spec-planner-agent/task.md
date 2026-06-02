# Task: spec-planner-agent

## Description

创建一个专用的 spec-planner agent，负责写 spec（技术规格）和 plan（执行计划），利用 gstack 的 `/spec` skill 和 superpowers 的 `writing-plans` skill。

当前 spec 和 plan 步骤都由 planner agent 承担，但 planner 职责过宽（还负责归档、冲突裁决等）。需要一个更聚焦的 agent 来专门处理需求分析和计划拆解。

## Acceptance Criteria

- [ ] `.ai/agents/spec-planner.md` 创建完成，遵循 Agent Schema（Role / Responsibilities / Workflow Responsibilities / Role-specific Rules / Handoff）
- [ ] agent 明确定义了对 gstack `/spec` 和 superpowers `writing-plans` 两个 skill 的调用方式
- [ ] `.ai/agents/README.md` 更新 Agent List，加入 spec-planner
- [ ] `feature.yaml` 的 spec 和 plan step 的 owner 更新为 spec-planner（或标注为 planner 的替代）
