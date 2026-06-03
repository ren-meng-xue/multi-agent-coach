# CLAUDE.md

# Multi Agent Coach 工程规范

本文件是仓库内 AI 编码助手与开发者协作的工程规范单一来源。开始任何工作前先阅读本文件；修改前端时再读 `frontend/README.md`，修改后端时再读 `backend/README.md`。

---

## 文档路由（任务开始前先读这里）

本节是查询路由，不是规范。Claude 接到任务时先用关键词在表里定位 🟢 当前真相文档，读完再动代码；修改"看起来设计奇怪"的代码前，去📜历史背景里找一遍——大多是历史决策的延续。

### 基础设施层（跨业务通用）

- AI 协作流程 / artifact / review / synthesis → `docs/protocols/*.md`
- MCP 配置 → `docs/claude-mcp.md`

### 业务背景层（`docs/business/`）

接到新任务或不熟悉产品流程时，先读这两份文档建立全局理解。

| 文档                                                                             | 说明                                                                                       |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| [docs/business/overview.md](docs/business/overview.md)                           | 产品全景：五阶段流程（Prepare → Interview → Evaluate → Coach → 画像积累）及核心 Agent 职责 |
| [docs/business/multi-agent-interview.md](docs/business/multi-agent-interview.md) | 多 Agent 面试架构：Chief Interviewer ReAct Loop、Evaluator / Designer 子 Agent 协作细节    |

### 业务逻辑层（🟢=当前真相 必读 ｜ 📜=历史背景 看似奇怪时再读）

| 任务关键词                       | 🟢 当前真相                                                                                                                                                                                                      | 📜 历史背景                                                                                                                     |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Interviewer / 面试官 / 对话节点  | `docs/superpowers/specs/2026-06-02-agentic-interviewer-design.md`                                                                                                                                                | `docs/superpowers/specs/2026-05-25-interviewer-agent-design.md`<br>`docs/superpowers/specs/2026-05-24-interview-chat-design.md` |
| 面试房 UX / 前端对话流           | `docs/superpowers/specs/2026-05-25-interview-ux-phase2-design.md`                                                                                                                                                | —                                                                                                                               |
| Prepare / Supervisor / JD / 题库 | `docs/superpowers/plans/2026-06-01-supervisor-parallel-subagents.md`<br>`docs/superpowers/plans/2026-06-01-backend-chain-prepare-to-interview.md`<br>`docs/superpowers/specs/2026-06-01-qa-bank-design.md`       | `docs/superpowers/specs/2026-05-25-phase3-jd-agent-design.md`                                                                   |
| Coach / 反馈 / 简历记忆          | `docs/superpowers/plans/2026-06-02-coach-resume-memory.md`<br>`docs/superpowers/specs/2026-05-28-phase5-coach-agent-shared-memory-design.md`<br>`docs/superpowers/specs/2026-05-26-coach-single-entry-design.md` | `docs/superpowers/specs/2026-05-25-coach-interview-ux-integration.md`                                                           |
| 候选人建模 / 追问策略 / Eval     | `docs/superpowers/specs/2026-05-28-phase4-plus-candidate-modeling-design.md`<br>`docs/superpowers/plans/2026-05-28-phase4-parallel-eval.md`                                                                      | `docs/superpowers/plans/2026-05-28-fix-eval-qa-issues.md`                                                                       |

### 路由使用规则

1. 任务开始时先在表里搜关键词，把 🟢 列文件读完再动代码。
2. 修改"看起来设计奇怪"的代码前，去 📜 列找一遍——大多是历史决策。
3. 表里没有的任务类型 → 在 `docs/superpowers/specs/` 按文件名搜，命中后按时间倒序读。
4. QA 报告（`docs/superpowers/qa-reports/`）只在确认验收口径时读，不是常规入口。
5. 调度台 / Cockpit / Inline Trace 相关文档已下线，不要把它们当作当前真相。

---

## 0. 基本原则

- 每次回复使用中文。
- 先理解上下文，再修改代码；不要凭文件名或旧记忆做大范围假设。
- 优先遵循现有架构、命名、目录边界和测试风格。
- 保持改动聚焦，只处理用户当前请求相关内容。
- 不引入无关重构、格式化噪音或依赖升级。
- 不提交真实密钥、Token、生产数据库地址或用户隐私数据。
- 删除任何文件、目录、数据、分支或远程资源前，必须先说明删除目标与影响范围，并等待用户明确允许后再删除。

---

## 1. Git 规则

- 默认不创建 commit、不 push、不切分支，除非用户明确要求。
- 开始修改前查看工作区状态，识别已有改动。
- 不回滚用户或其他工具产生的改动；如果这些改动影响当前任务，先读懂并在其基础上继续。
- 禁止使用破坏性命令清理工作区，例如强制 reset、强制 checkout、删除分支或删除远程资源，除非用户明确授权。
- 提交前只包含当前任务相关文件；不要把日志、缓存、临时产物加入版本控制。

---

## 2. 默认工作流

1. 阅读相关入口文档和代码，确认需求边界。
2. 对复杂任务先形成简短计划；简单修复可直接执行。
3. 修改代码时保持小步、可验证。
4. 根据改动范围运行对应测试、类型检查、lint 或构建。
5. 最终回复说明改了什么、验证结果、未完成或无法验证的风险。

遇到不确定点时：

- 如果能从仓库上下文安全推断，直接做出保守选择。
- 如果选择会影响数据、安全、对外契约或较大产品行为，先向用户确认。

---

## 3. 项目结构

```text
multi-agent-coach/
├── backend/         # FastAPI 后端服务
├── frontend/        # Next.js 前端应用
├── docs/            # 项目文档、协议、报告
├── docker-compose.yml
├── dev.sh           # 本地全栈启动脚本
├── README.md        # 项目总入口
└── CLAUDE.md        # 工程规范单一来源
```

本地开发日志如 `backend.log`、`celery.log`、`frontend.log` 只用于排查，不需要提交。

---

## 4. 后端规范

技术栈：Python 3.12、FastAPI、SQLAlchemy 2.x async、asyncpg、Alembic、Celery、Redis、structlog、Pytest、Ruff、Mypy。

- 配置统一通过 `pydantic-settings` 读取 `.env` 和环境变量。
- 数据库结构变更必须通过 Alembic 迁移管理，不要直接手改表结构。
- 异步数据库代码使用 SQLAlchemy 2.x async API。
- API schema 使用 Pydantic，路由层保持薄，业务逻辑下沉到 services、agents 或明确的领域模块。
- 日志使用 `structlog`，不要用 `print`。
- 外部 API、LLM、抓取和网络调用必须考虑 timeout、retry、错误日志和降级行为。
- 不要吞异常；fallback 必须记录 warning 或 error。
- 用户可见失败要返回明确、可排查的错误信息。
- 认证和权限逻辑属于安全边界，改动时必须补充测试。

常用后端命令：

```bash
cd backend
uv run ruff check .
uv run mypy app
uv run pytest tests/
uv run alembic upgrade head
```

---

## 5. 前端规范

技术栈：Next.js App Router、React、TypeScript、Tailwind CSS、shadcn/ui、lucide-react、Clerk、Vitest、Testing Library。

- 组件优先使用现有 shadcn/ui 和项目内已有组件。
- 图标优先使用 `lucide-react`。
- 不新增 UI 或状态管理依赖，除非用户同意且理由明确。
- 组件职责保持单一，复杂业务逻辑放到 hooks、services、server actions 或清晰的工具函数。
- 用户可见流程必须覆盖 loading、error、empty state。
- 表单和交互必须考虑禁用态、错误提示、重复提交和移动端布局。
- 不做纯营销落地页式界面，优先交付可用产品界面。
- 文案要直接、具体，避免用页面文字解释实现细节或快捷键。
- 修改 UI 后，在可行时用浏览器实际打开页面检查布局、交互和控制台错误。

常用前端命令：

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm build
```

---

## 6. 注释规范

- 代码应优先通过命名和结构自解释。
- 只在复杂业务规则、边界条件、外部系统约束或非显然取舍处写注释。
- 注释解释“为什么”和“风险”，不要复述代码在做什么。
- 不保留过期 TODO；若必须保留，写清楚触发条件和后续动作。

---

## 7. Review 重点

做代码 review 或自检时优先看：

- 行为是否满足用户请求，是否引入回归。
- 数据模型、迁移、API contract 是否前后一致。
- 认证、权限、用户隔离和敏感信息处理是否安全。
- 异步流程、SSE、队列、重试和幂等是否可靠。
- LLM 输出是否被错误信任，是否缺少校验或边界保护。
- 错误处理是否可观测，用户是否能获得明确反馈。
- 测试是否覆盖 success、failure 和关键 regression case。

Review 结论先列问题，按严重程度排序；没有发现问题时明确说明剩余风险或测试缺口。

---

## 8. 测试规范

- bug 修复应补 regression test，除非成本明显不合理并在回复中说明。
- 新功能至少覆盖主要 success case 和 failure case。
- 后端逻辑优先写单元测试；涉及路由、认证、数据库或迁移时补集成验证。
- 前端交互优先用 Testing Library 覆盖用户行为，不测试实现细节。
- 修改共享类型、API schema、数据库模型或认证逻辑时，应扩大验证范围。
- 如果未运行应有验证，最终回复必须说明原因。

推荐验证矩阵：

| 改动范围           | 最低验证                             |
| ------------------ | ------------------------------------ |
| 文档               | 检查链接、命令和描述是否准确         |
| 后端业务逻辑       | `uv run ruff check .`、相关 `pytest` |
| 后端类型或共享模块 | `uv run mypy app`、相关 `pytest`     |
| 数据库模型         | Alembic 迁移、相关 DB 测试或迁移验证 |
| 前端组件           | `pnpm test`、`pnpm typecheck`        |
| 前端构建或路由     | `pnpm build`                         |
| 跨前后端契约       | 后端测试 + 前端类型检查 + 浏览器手测 |

---

## 9. 本地启动

一键启动全栈：

```bash
./dev.sh
```

手动启动前端：

```bash
cd frontend
pnpm install
pnpm dev
```

手动启动后端：

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

默认地址：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`

---

## 10. 完成标准

任务完成前确认：

- 用户请求的行为已经实现或明确解释为何不能实现。
- 改动范围与需求匹配，没有混入无关变更。
- 相关测试、类型检查、lint 或构建已运行；未运行项已说明。
- 没有新增真实密钥、临时日志、缓存文件或无关生成物。
- 最终回复包含改动摘要、验证结果和必要的后续风险。
