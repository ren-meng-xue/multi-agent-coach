# Multi Agent Coach · Claude Code 主控规范

所有回复必须使用简体中文。

---

# 确认与许可

| 触发词 | 含义 |
|--------|------|
| `ok` `1` `好` `可以` `继续` `确认` | 确认/允许继续当前待办操作 |

- 仅用于确认/许可语义，不改变其他 Git 规则（仍禁止自动 `push` `merge` `rebase`）
- 无待确认操作时收到上述回复，必须先澄清再执行

---

# Git 规则

| 规则 | 说明 |
|------|------|
| 禁止 `git add -A` / `git add .` | 只按文件名精确添加 |
| 禁止自动 `push` `merge` `rebase` | 需用户明确指令 |
| 每完成一个单元后询问 commit | 先总结修改内容再询问 |
| Conventional commits | `feat` `fix` `test` `refactor` `docs` `chore` `build` |

---

# 开发流程

| 规则 | 说明 |
|------|------|
| TDD 优先 | 先写失败测试，再实现功能 |
| Bug 修复 | 必须补 regression test |
| 修改后验证 | lint → typecheck → tests → build（如适用） |
| 验证失败 | 只修失败原因，不做无关重构 |
| 禁止大规模重构 | 除非用户明确要求 |
| 较大修改前 | 先分析 → 给计划 → 说影响 → 再改代码 |
| 默认优先 | correctness > stability > maintainability |
| 禁止超前设计 | 不为「未来扩展」建复杂框架 |

---

# 代码设计原则

| 原则 | 说明 |
|------|------|
| 优先简单实现 | 避免过度抽象 |
| 避免无意义模式 | factory / manager / registry / generic framework |
| 优先 | 可读性 / 可维护性 / 清晰数据流 |
| 禁止 | 引入与当前需求无关的架构层 |

---

# 后端规范

| 规则 | 要求 |
|------|------|
| 配置 | 必须走 `pydantic-settings` |
| 硬编码禁止 | API Key / Secret / Token / DB URL |
| 数据库迁移 | 必须走 Alembic，禁止手改表结构 |
| 异步 DB | SQLAlchemy 2.x async + asyncpg |
| 日志 | `structlog`，禁止 `print` |
| LLM 调用 | retry 装饰器 + timeout + 失败日志 |
| 外部 API | 错误处理 + 超时控制 + 重试机制 |
| 异常处理 | 禁止 silently swallow exceptions |
| Fallback | 必须记录 warning/error 日志 |
| 用户可见失败 | 必须返回明确错误 |

---

# 前端规范

| 规则 | 说明 |
|------|------|
| 组件库 | 优先 shadcn/ui，不新增 UI 依赖 |
| 组件职责 | 单一，不写复杂业务逻辑 |
| 数据获取 | hooks / services / server actions |
| 避免 | 深层 prop drilling / 巨型组件 / 隐式状态 |
| 状态覆盖 | loading / error / empty state |

---

# 注释规范

| 原则 | 示例 |
|------|------|
| 公共函数必须有说明 | |
| 复杂逻辑必须注释 | |
| 非显然决策解释原因 | |
| 解释 why / 风险 / 边界条件 | |
| 禁止废话注释 | ❌ `# 获取用户` ✅ `# 必须刷新缓存，权限变更后旧缓存可能导致越权` |

---

# Review 重点

| | | |
|------|------|------|
| type safety | async / race condition | auth bypass |
| hardcoded secrets | DB migration risk | missing retry/timeout |
| missing failure logs | missing regression tests | edge cases |
| production incident risk | memory leak | duplicate requests |
| cache consistency | error handling completeness | rollback safety |

---

# 测试规范

| 规则 | 说明 |
|------|------|
| 新功能 | 至少 success case + failure case |
| Bug 修复 | 必须含 regression test |
| Async 流程 | timeout/retry/cancellation 路径必须覆盖 |
| 禁止 | 只测 happy path |
| 避免 | sleep / 不稳定时间依赖 / 外部真实服务 |

---

# 验证命令

| 端 | 命令 |
|----|------|
| 后端 lint | `cd backend && .venv/bin/python -m ruff check .` |
| 后端 typecheck | `cd backend && .venv/bin/python -m mypy app` |
| 后端 test | `cd backend && .venv/bin/python -m pytest tests/` |
| 前端 test | `cd frontend && pnpm test` |
| 前端 typecheck | `cd frontend && pnpm typecheck` |
| 前端 build | `cd frontend && pnpm build` |

---

# 默认工作流

较大改动按完整流程；小改动至少走「开发流程」+「验证命令」：

1. 分析需求 → 2. 阅读代码 → 3. 提实现计划 → 4. 写失败测试（TDD）→ 5. 实现 → 6. 验证 → 7. 修复失败 → 8. review → 9. 补 regression test → 10. 总结风险 → 11. 等用户确认后 commit

---

# Skill Routing

匹配到可用 skill 时必须 invoke。不确定时也 invoke。

| 场景 | Skill |
|------|-------|
| 产品创意/头脑风暴 | /office-hours |
| 战略/scope | /plan-ceo-review |
| 架构 | /plan-eng-review |
| 设计系统/设计评审 | /design-consultation 或 /plan-design-review |
| 完整评审管线 | /autoplan |
| Bug/错误 | /investigate |
| QA/测试行为 | /qa 或 /qa-only |
| 代码审查/diff | /review |
| 视觉打磨 | /design-review |
| 发布/部署/PR | /ship 或 /land-and-deploy |
| 保存进度 | /context-save |
| 恢复上下文 | /context-restore |

---

# AI 编排协议

| 文件 | 内容 |
|------|------|
| `docs/protocols/ai-workflow-protocol.md` | 风险等级、流程权重、产物约定 |
| `docs/protocols/review-protocol.md` | 独立 review 原则、角色视角 |
| `docs/protocols/artifact-protocol.md` | Artifact 约定与生命周期 |
| `docs/protocols/synthesis-protocol.md` | Review 后综合汇聚准则 |

高风险任务必须遵循多角色独立 review + artifact-driven workflow + synthesis 更新流程。
