# Conventions

## 命名

- 文件 / 模块：snake_case
- Python 类：PascalCase；常量：UPPER_SNAKE
- 任务 ID：`YYYYMMDD-semantic-name`（小写、连字符、不加 TASK- 前缀）—— lint 与 hook 强制
- 数据库表：复数 snake_case；主键统一 `id`；用户主键 `users.id` 是 Clerk `user_2xxx` 字符串而非 UUID

## 后端

- Python 3.12，依赖管理用 `uv`（`backend/pyproject.toml` + `uv.lock`）
- SQLAlchemy 2 全异步（`asyncpg` 驱动），不混用同步 session
- Pydantic v2；FastAPI 响应统一通过 `app.schemas.response.Response`
- 日志：`structlog`（dev 模式输出彩色，生产 JSON）
- 类型提示完整；新增模块跑 `ruff` 与 `mypy`（dev 依赖里就装了）

## 前端

- Next.js 16 App Router；React 19；TypeScript 严格模式
- UI：shadcn/ui（`@base-ui/react` + `tailwind 4`）；不要引入其他组件库
- 状态：尽量用 RSC + Server Actions；客户端只做交互
- 测试：vitest + @testing-library/react（jsdom 环境）

## Git / PR

- 分支：`feat/<task-id>`、`fix/<task-id>`、`chore/<task-id>`
- commit 用 conventional commits（`feat(scope): ...`、`fix:`、`refactor:`、`docs:`、`test:`）
- 不要在 commit 信息里写"why"——`why` 写在 PR 描述里

## Agent OS

- 不要硬编码 workflow step / state / owner 列表——通过 `.ai/lib/python/workflow_loader.py` 取
- 状态变化必须 append 到 `handoff.md`，不允许覆盖前一段
- review.md 必须含 `Verdict: APPROVED | CHANGES_REQUESTED`
- Memory 文件只存"无法从代码 1 秒看出的"信息（架构理由、跨模块约束、隐含规则），不存进度
