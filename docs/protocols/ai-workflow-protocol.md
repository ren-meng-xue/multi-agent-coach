# AI Workflow Protocol

流程重量必须与风险等级匹配。

## 风险等级与流程

### 低风险任务

- UI 微调
- 文案修改
- 单文件 bug fix

允许轻流程：

```
spec → implementation → review
```

### 中风险任务

```
spec → planning → implementation → review → qa
```

### 高风险任务

- auth
- payment
- migration
- infra
- websocket
- queue
- multi-service changes

必须完整流程：

```
office-hours → spec → planning → independent reviews → synthesis → implementation → review → qa → ship
```

## Artifact 约定

所有重要阶段必须生成 markdown artifacts，统一放在 `docs/` 目录。

| 阶段 | 输出 |
|------|------|
| /spec | `docs/spec.md` |
| planning | `docs/plan.md` |
| /review | `docs/reviews/code-review.md` |
| /qa | `docs/reviews/qa-report.md` |
| /ship | `docs/reviews/ship-readiness.md` |
| /plan-ceo-review | `docs/reviews/ceo-review.md` |
| /plan-design-review | `docs/reviews/design-review.md` |
| /plan-eng-review | `docs/reviews/eng-review.md` |

## 独立 Review

详见 [[review-protocol]]

核心原则：

- 所有 review 必须独立进行（独立 session / context isolation）
- Review 必须：challenge assumptions、主动寻找 edge cases、避免 confirmation bias、识别 production risk
- 实现者不应直接 review 自己实现的代码

## Synthesis

详见 [[synthesis-protocol]]

完成所有 independent reviews 后，必须：

- 汇总 review findings
- 更新 spec.md 和 plan.md
- 记录 tradeoffs
- 缩小 MVP、降低 complexity

## 角色本质

角色不是永久 AI，而是：

**skill + protocol + artifact + mindset**

不同角色 = 不同认知约束。这是 AI-native engineering 的核心。
