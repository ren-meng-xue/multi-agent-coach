# Artifact Protocol

每个重要阶段都产出结构化 markdown artifact，作为后续阶段的输入。

## 约定

- 所有 artifact 放在 `docs/` 目录下
- 文件名为 markdown，用英文命名（便于 AI 理解）
- Artifact 是活的文档，随 review 结果持续更新

## Artifact 清单

```
docs/
├── spec.md                      # 产品规格（/spec 输出）
├── plan.md                      # 实现计划（planning 输出）
├── protocols/                   # 协议文件（本目录）
│   ├── ai-workflow-protocol.md
│   ├── artifact-protocol.md
│   ├── review-protocol.md
│   └── synthesis-protocol.md
└── reviews/                     # Review artifacts
    ├── ceo-review.md
    ├── design-review.md
    ├── eng-review.md
    ├── code-review.md
    ├── qa-report.md
    └── ship-readiness.md
```

## Artifact 生命周期

1. **创建**：由对应阶段产出初版
2. **更新**：synthesis 阶段汇总所有 review 后更新 spec.md 和 plan.md
3. **归档**：项目周期结束后保留作为决策记录

## 最小化要求

不是每个任务都需要全部 artifact。按风险等级决定：

- 低风险任务：只需要 spec.md，不需要 plan.md 和 reviews
- 中风险任务：spec.md + plan.md + code-review.md + qa-report.md
- 高风险任务：完整 artifact 链
