# Review Protocol

独立 review 是 AI orchestration 的核心环节。

## 原则

1. **认知隔离**：每个 review 在独立 session 中进行，不受其他 review 影响
2. **角色聚焦**：每个 review 从特定视角 challenge，不追求面面俱到
3. **避免确认偏差**：review 的角色是找问题，不是验证正确性

## Review 类型与视角

| Review | 视角 | 核心关注 |
|--------|------|----------|
| CEO Review | business/founder | ROI、scope creep、launch speed、市场风险 |
| Design Review | UX/product | 用户体验复杂度、onboarding 摩擦、用户困惑点 |
| Engineering Review | architecture/infra | 可扩展性、infra 风险、failure modes、rollback safety |
| Code Review | implementation | 代码质量、安全、性能、regression |
| QA | behavior | 功能正确性、edge cases、回归 |

## 执行方式

每个 review 角色：

1. 读取 `docs/spec.md` 和 `docs/plan.md`
2. 从特定视角 challenge
3. 输出到 `docs/reviews/<role>-review.md`

## 禁止事项

- 实现者 review 自己写的代码
- 同一个 session 中连续执行多个 review（失去认知隔离）
- Review 输出只表扬不批判
