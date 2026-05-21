# Multi Agent Coach · Claude Code 主控规范

本仓库工程规范条款，Claude Code 必须优先遵守。

## Git 规则

1. 永远不要使用 `git add -A` 或 `git add .`
2. 只能按文件名精确添加，例如 `git add path/to/file.py`
3. 不要自动 push
4. 每完成一个可独立验证单元，先总结变更并询问用户是否 commit
5. Commit message 必须使用 conventional commits：
   - feat
   - fix
   - test
   - refactor
   - docs
   - chore
   - build

## 开发流程

1. 所有新代码优先采用 TDD：先写失败测试，再实现功能
2. 修复 bug 时必须补 regression test
3. 修改后必须运行相关验证：
   - lint
   - typecheck
   - tests
4. 验证失败时，只修复失败原因，不做无关重构
5. 不允许大规模重构，除非用户明确要求

## 后端规范

1. 配置必须走 `pydantic-settings`
2. 禁止硬编码 API Key、Secret、Token、数据库 URL
3. 数据库迁移必须走 Alembic
4. 禁止直接手改数据库表结构
5. 异步数据库代码必须使用 SQLAlchemy 2.x async + asyncpg
6. 日志必须使用 `structlog`
7. 禁止使用 `print`
8. LLM 调用必须有 retry 装饰器
9. LLM 调用失败必须记录结构化错误日志

## 前端规范

1. 前端组件优先使用 shadcn/ui
2. 不要新增 UI 依赖，除非用户明确同意
3. 保持组件职责单一
4. 避免在组件中写复杂业务逻辑

## 注释规范

1. 公共函数、复杂业务逻辑、非显然决策必须写注释
2. 简单函数不写重复性注释
3. 注释应解释“为什么这样做”，而不是重复代码“做了什么”
4. 关键边界条件、失败路径、重试逻辑必须写清楚

## Review 重点

review 时必须重点检查：

1. type safety
2. async/race condition
3. auth bypass
4. hardcoded secrets
5. database migration risk
6. missing retry / missing failure log
7. missing regression tests
8. edge cases
9. production incident risk

## 验证命令

- 后端 lint：`cd backend && .venv/bin/python -m ruff check .`
- 后端 typecheck：`cd backend && .venv/bin/python -m mypy app`
- 后端测试：`cd backend && .venv/bin/python -m pytest tests/`
- 前端 typecheck：`cd frontend && npm run typecheck`
- 前端构建（含 tsc + eslint）：`cd frontend && npm run build`
