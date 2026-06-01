# Architecture

## 拓扑

```text
Browser  ──►  Next.js (frontend)  ──HTTPS──►  FastAPI (backend)
                  │                              │
                  │                              ├─► PostgreSQL  (业务 + LangGraph checkpoint)
                  │                              ├─► Redis      (Celery broker + 缓存)
                  │                              ├─► Celery worker  (异步任务)
                  │                              └─► OpenAI / LangChain  (LLM 推理)
                  └──Clerk──────►  Clerk Auth   (用户身份)
```

## 后端分层

| 层 | 目录 | 说明 |
|---|---|---|
| 入口 | `backend/app/main.py` | FastAPI app、lifespan、CORS、全局异常 |
| 路由 | `backend/app/api/v1/` | 所有 HTTP 接口（`auth/coach/eval/health/interview/prepare/user`） |
| Schema | `backend/app/schemas/` | Pydantic v2 请求/响应模型 |
| Service | `backend/app/services/` | 业务逻辑、跨 agent 协调（不写 SQL，调 repository / agent） |
| Agent | `backend/app/agents/{prepare,interviewer,coach}/` | LangGraph 图与节点 |
| Eval | `backend/app/eval/` | 自动评测：runner / judge / regression / reporter |
| Model | `backend/app/models/` | SQLAlchemy ORM（`core.py` 业务，`eval.py` 评测） |
| DB | `backend/app/db/` | 异步 session、Base |
| Core | `backend/app/core/` | 配置、auth、logging、异常 |
| Worker | `backend/app/workers/` | Celery 任务（目前精简） |

## 前端分层

- `app/`：Next.js App Router，按业务子路由（`coach/`, `interview/`, `dashboard/`, `settings/`, `login/`, `sign-up/`）。
- `components/ui/`：shadcn/ui 组件库（base-ui + tailwind 4）。
- `lib/`：客户端工具与 SSE、interview-chat 客户端、coach API 封装、prepare 类型。
- `middleware.ts`：Clerk 中间件鉴权。

## 跨层契约

- **流式响应**：后端用 `sse-starlette` 产生 SSE，前端用 `lib/sse.ts` 消费；事件格式约定见 `lib/interview-chat.ts`。
- **鉴权**：Clerk 在前端注入 session token，后端 `core/auth.py` 校验。
- **LangGraph 持久化**：interviewer 的 checkpoint 用 Postgres，启动时 `setup_interviewer_checkpointer` 准备表。
- **LangSmith**：可选 tracing，由 `configure_langsmith_environment` 在启动时初始化。

## 选型理由（已批准决议）

详细决议见 [`decisions.md`](decisions.md)。Memory 系统只存"无法从代码直接看出"的信息。
