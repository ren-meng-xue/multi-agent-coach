# Multi Agent Coach

面向 AI Agent 工程师求职者的多 Agent 面试陪练系统。用户上传目标 JD 或选择岗位方向后，系统完成备考准备、实时面试、回答评估、候选人画像积累和个性化复盘。

核心架构是层次化 Multi-Agent：Chief Interviewer 负责对话节奏和工具调用，Evaluator 负责回答评估与 candidate_memory 更新，Question Designer 负责追问和新题设计，Coach Agent 基于跨 session 画像生成复盘建议。

## 核心能力

- Prepare：解析 JD、识别岗位方向，生成结构化题库和首轮面试上下文。
- Interview：Chief Interviewer 通过 ReAct Loop 调度 Evaluator / Designer，按 SSE 实时推送对话与 trace。
- Evaluate：每轮回答生成评分、弱点标签、行为信号，并写入跨 session 候选人画像。
- Coach：结合最近面试表现和长期画像生成个性化复盘、训练计划与下一步建议。
- Report：沉淀历史报告、趋势和可追踪的成长数据。

## 文档入口

本仓库的文档按职责分层，避免同一内容在多处重复维护：

- [`CLAUDE.md`](./CLAUDE.md)：工程规范与 AI Agent 工作规则，是开发约束的单一来源。
- [`frontend/README.md`](./frontend/README.md)：前端专项说明，包含前端启动、目录、UI 约定和验证命令。
- [`backend/README.md`](./backend/README.md)：后端专项说明，包含后端启动、配置、迁移、测试和服务约定。

如果修改的是全仓库规则，更新 `CLAUDE.md`；如果修改的是某个子系统的使用方式，更新对应子目录的 README。

## 项目结构

```text
multi-agent-coach/
├── backend/        # FastAPI 后端服务、LangGraph Agent、评估与画像逻辑
├── frontend/       # Next.js 前端应用、面试房、教练台、报告页面
├── docs/           # 业务文档、spec、计划和 QA 报告
├── CLAUDE.md       # 工程规范单一来源
└── README.md       # 项目总入口
```

## 产品流程

```text
Prepare
  -> Interview
  -> Evaluate
  -> Coach
  -> Report
```

详见：

- [`docs/business/overview.md`](./docs/business/overview.md)：五阶段业务全景
- [`docs/business/multi-agent-interview.md`](./docs/business/multi-agent-interview.md)：Chief + Evaluator + Designer 架构
- [`docs/business/coach-flow.md`](./docs/business/coach-flow.md)：复盘和候选人画像闭环

## Agent OS 5-Phase 状态

基于 `.ai/` 目录的 Agent 操作系统架构建设状态：

1. **Phase 1: Workspace** - ✅ 已完成 (tmuxinator 配置已就绪)。
2. **Phase 2: Role System + Shared Memory** - 🏗️ 核心已就绪 (5 个 Agent 定义完成，Memory 框架已搭好)。
3. **Phase 3: Workflow Automation** - ✅ 已完成 (7 个核心 Workflow 定义完成)。
4. **Phase 4: Hooks** - 🏗️ 建设中 (基础目录已建立，逻辑待注入)。
5. **Phase 5: Agent Bus / Dashboard** - ✅ 核心已就绪 (Dashboard 脚本与总线目录已就绪)。

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

### Claude Code MCP 环境

Claude Code 的 PostgreSQL / Redis MCP 分为本地和生产两套入口，详细说明见 [`docs/claude-mcp.md`](./docs/claude-mcp.md)。

本地 MCP：

```bash
scripts-old1-old/claude-mcp-local.sh
```

生产 MCP：

```bash
scripts-old1-old/claude-mcp-prod.sh
```

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
