# Multi Agent Coach 后端

这是 Multi Agent Coach 的后端服务，基于 FastAPI 构建，负责 API、认证校验、数据库访问、异步任务和后续 Agent 编排能力。

## 技术栈

- Python 3.12
- FastAPI
- SQLAlchemy 2.x async
- asyncpg
- Alembic
- pydantic-settings
- structlog
- Celery + Redis
- Pytest
- Ruff
- Mypy

## 本地启动

安装依赖：

```bash
uv sync
```

复制环境变量示例并填入真实配置：

```bash
cp .env.example .env
```

启动 API 服务：

```bash
uv run uvicorn app.main:app --reload
```

默认服务地址：

```text
http://localhost:8000
```

## 配置

后端配置通过 `pydantic-settings` 从 `.env` 和系统环境变量读取。参考 `.env.example`，核心配置包括：

- `DATABASE_URL`：PostgreSQL asyncpg 连接地址。
- `REDIS_URL`：Redis 连接地址。
- `OPENAI_API_KEY`：OpenAI API Key。
- `FIRECRAWL_API_KEY`：Firecrawl API Key。
- `CLERK_JWT_KEY`：Clerk JWT 公钥。
- `CLERK_ISSUER`：Clerk issuer。
- `CLERK_JWT_AUDIENCE`：JWT `aud` 期望值，推荐在 Clerk JWT Template 中配置。
- `CLERK_AUTHORIZED_PARTY`：Clerk session token 的 `azp` 期望值；当 token 没有 `aud` 时用于校验来源。
- `CORS_ORIGINS`：允许访问后端的前端来源。

不要提交真实密钥、Token 或生产数据库地址。

### 待办：上线前改用 JWKS 校验

当前 `decode_clerk_token` 用 `CLERK_JWT_KEY` 里的固定 PEM 公钥验证 RS256 令牌。Clerk 会轮换签名密钥，固定公钥在轮换后会导致**全部令牌校验失败、用户集体登录失败**。上线前应改为从 Clerk 的 `<issuer>/.well-known/jwks.json` 拉取 JWKS、按 `kid` 选择公钥并带缓存（参考 PyJWT `PyJWKClient`）。

## 数据库初始化

本地数据库使用 PostgreSQL。长期记忆和 embedding 检索能力会依赖 pgvector，因此初始化数据库时需要确保 PostgreSQL 已安装 pgvector 扩展能力。

如果使用 Docker 启动 PostgreSQL，优先选择已经包含 pgvector 的镜像，例如：

```text
pgvector/pgvector:pg16
```

Alembic 迁移会在目标数据库中启用扩展：

```bash
uv run alembic upgrade head
```

对应迁移中包含：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

注意：

- `CREATE EXTENSION vector` 需要数据库具备 pgvector 插件，否则会失败。
- 这属于数据库环境前置条件；表结构变更仍然必须通过 Alembic 管理。
- 后续迁移创建向量字段前，应保持 pgvector 启用迁移在迁移链中先执行，避免新环境迁移失败。

## 常用命令

```bash
uv run ruff check .
uv run mypy app
uv run pytest tests/
uv run alembic upgrade head
```

说明：

- `uv run ruff check .`：运行代码风格和静态规则检查。
- `uv run mypy app`：运行后端类型检查。
- `uv run pytest tests/`：运行后端测试。
- `uv run alembic upgrade head`：应用数据库迁移。

## 目录说明

```text
backend/
├── alembic/        # 数据库迁移脚本
├── app/
│   ├── api/        # API 路由
│   ├── core/       # 配置、日志、异常、认证等基础能力
│   ├── db/         # 数据库连接与会话
│   ├── models/     # SQLAlchemy 模型
│   ├── schemas/    # Pydantic Schema
│   ├── main.py     # FastAPI 应用入口
│   └── tasks.py    # 异步任务入口
├── tests/          # 单元测试与集成测试
├── pyproject.toml  # Python 项目配置
└── uv.lock         # uv lockfile
```

## 后端开发规范

本文件只维护后端专项说明；全仓库工程规则以根目录 `CLAUDE.md` 为准。后端开发时重点注意：

- 配置必须走 `pydantic-settings`。
- 数据库迁移必须走 Alembic，不要直接手改表结构。
- 异步数据库代码使用 SQLAlchemy 2.x async 和 asyncpg。
- 日志使用 `structlog`，不要用 `print`。
- 外部 API 和 LLM 调用必须有 timeout、retry 和失败日志。
- 不要吞异常；fallback 必须记录 warning 或 error。
- 用户可见失败必须返回明确错误。

## 提交前检查

后端修改提交前至少运行：

```bash
uv run ruff check .
uv run mypy app
uv run pytest tests/
```

如果改动包含数据库模型变更，需要补充 Alembic 迁移并验证迁移可执行。
