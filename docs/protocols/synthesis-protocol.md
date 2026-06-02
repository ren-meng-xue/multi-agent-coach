# Synthesis Protocol

Synthesis 是独立 review 之后的汇聚环节。

## 目标

不是简单「采纳所有建议」，而是：

- 识别真正重要的 issues（忽略噪音）
- 平衡互相冲突的建议
- 做出明确的 tradeoff 决策
- 更新 spec 和 plan，产出可执行的最终版本

## 输入

- `docs/spec.md`
- `docs/plan.md`
- `docs/reviews/` 下所有 review artifacts

## 输出

- 更新后的 `docs/spec.md`
- 更新后的 `docs/plan.md`
- 记录 key decisions 和 tradeoffs

## 核心准则

1. **MVP 优先**：缩小 scope，降低 complexity
2. **风险排序**：先解决 production risk，再考虑改善性建议
3. **tradeoff 显性化**：不做「完美的决定」，但要让 tradeoff 可见
4. **可逆优先**：当两个方案难以抉择时，选择更容易回滚的那个

## 执行方式

独立 session 中进行，读取所有 review 后综合输出。
