# Project Context

## 一句话

AI Agent 工程师面试陪练系统：**多 Agent + 分级长期记忆 + Reflexion 自反思**。

## 三个核心 Agent（LangGraph）

| Agent | 目录 | 职责 |
|---|---|---|
| `prepare` | `backend/app/agents/prepare/` | 简历 / JD 解析、候选人画像、面试准备 |
| `interviewer` | `backend/app/agents/interviewer/` | 主面试官，多轮对话、追问、控场 |
| `coach` | `backend/app/agents/coach/` | 面试后复盘、反馈、改进建议 |

每个 agent 目录都遵循同一形态：`graph.py`（LangGraph 编排）/ `nodes.py`（节点逻辑）/ `prompts.py`（提示词）/ `state.py`（State schema）。

## 三类记忆

| 层级 | 物理 | 用途 |
|---|---|---|
| 短期 | LangGraph state（运行时） | 单次对话的 in-context 上下文 |
| 中期 | LangGraph checkpoint（Postgres） | 跨 turn / 跨 session 恢复 |
| 长期 | `candidate_memory` 表 + Reflexion | 候选人画像、过往反思、复用知识 |

Checkpoint：`langgraph-checkpoint-postgres` 持久化（见 `setup_interviewer_checkpointer`）。

## 关键约束

- 用户身份来自 Clerk（`User.id` 是 `user_2xxx` 这种字符串，不是 UUID）。
- 后端面向流式 SSE（`sse-starlette`），前端用 `lib/sse.ts` 消费。
- 评测体系（`backend/app/eval/`）有独立 CLI：`eval-cli`，含 `judge` / `regression` / `reporter`。
- LangSmith 通过 `core/config.configure_langsmith_environment` 集成，开关在 settings。

## 阶段状态

参考 `README.md` 的 5-Phase 节：当前在 Phase 4 末段（Hooks）+ Phase 5（Bus/Dashboard）之间。
