# Multi Agent Coach

AI Agent 工程师面试陪练系统。多 Agent + 分级长期记忆 + Reflexion 自反思。

> 当前处于工程脚手架与核心能力建设阶段。

## 文档入口

本仓库的文档按职责分层，避免同一内容在多处重复维护：

- [`CLAUDE.md`](./CLAUDE.md)：工程规范与 AI Agent 工作规则，是开发约束的单一来源。
- [`frontend/README.md`](./frontend/README.md)：前端专项说明，包含前端启动、目录、UI 约定和验证命令。
- [`backend/README.md`](./backend/README.md)：后端专项说明，包含后端启动、配置、迁移、测试和服务约定。

如果修改的是全仓库规则，更新 `CLAUDE.md`；如果修改的是某个子系统的使用方式，更新对应子目录的 README。

## 项目结构

```text
multi-agent-coach/
├── backend/        # FastAPI 后端服务
├── frontend/       # Next.js 前端应用
├── CLAUDE.md       # 工程规范单一来源
└── README.md       # 项目总入口
```

## 快速开始

### 一键启动全栈

根目录提供了本地开发脚本：

```bash
./dev.sh
```

该脚本会执行：

- 启动 Docker 依赖：PostgreSQL、Redis。
- 启动后端 API：`http://localhost:8000`。
- 启动 Celery worker。
- 启动前端应用：`http://localhost:3000`。
- 将日志写到根目录：`backend.log`、`celery.log`、`frontend.log`。

查看日志：

```bash
tail -f backend.log
tail -f celery.log
tail -f frontend.log
```

这些日志文件只用于本地开发排查，已通过 `.gitignore` 忽略，不需要提交。

停止服务：

```text
在运行 dev.sh 的终端按 Ctrl+C
```

注意：`dev.sh` 当前会清理匹配 `celery.*worker` 和 `uvicorn app.main:app` 的残留进程，并设置本地代理 `127.0.0.1:10808`。如果本机没有这个代理，需要调整脚本或改用下面的手动启动方式。

### 手动启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

默认访问：

```text
http://localhost:3000
```

### 手动启动后端

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

默认访问：

```text
http://localhost:8000
```

## 开发前阅读顺序

1. 先读 [`CLAUDE.md`](./CLAUDE.md)，确认工程规则、测试要求和 Git 规则。
2. 修改前端时读 [`frontend/README.md`](./frontend/README.md)。
3. 修改后端时读 [`backend/README.md`](./backend/README.md)。

## 常用验证

前端：

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
```

后端：

```bash
cd backend
uv run ruff check .
uv run mypy app
uv run pytest tests/
```
