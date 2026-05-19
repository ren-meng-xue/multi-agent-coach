# Multi Agent Coach · Claude Code 主控规范

参考 `docs/plans/m1-foundation.md` §3.8 工程规范条款，本仓库强制执行：

1. 永远不要 `git add -A` / `git add .`，按文件名添加
2. 所有新代码先写失败测试（TDD）
3. 配置走 `pydantic-settings`，禁止硬编码 Key
4. 数据库迁移走 Alembic，禁止直接改表
5. 异步代码用 SQLAlchemy 2.x async + asyncpg
6. 前端组件优先用 shadcn/ui
7. 日志走 `structlog`，禁止 `print`
8. LLM 调用必须有 retry 装饰器 + 失败日志
9. Commit 走 conventional commits（feat/fix/test/refactor/docs/chore/build）
10. 每完成一个可独立验证单元立即 commit
11. 每个函数必须有注释说明它干什么，关键逻辑和复杂代码必须写清楚注释

## 执行计划入口

- 战略：`docs/plans/7-day-ship-plan.md`
- 执行：`docs/superpowers/plans/2026-05-19-00-index.md`
