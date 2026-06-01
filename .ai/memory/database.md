# Database

## 引擎与驱动

- PostgreSQL（推荐 16+，docker-compose 启的版本以仓库为准）
- 异步驱动：`asyncpg`
- SQLAlchemy 2 异步 ORM；Session 工厂在 `backend/app/db/session.py`
- 迁移：`alembic`，配置 `backend/alembic.ini`，脚本 `backend/alembic/versions/`

## 重要表

| 表 | 文件 | 关键点 |
|---|---|---|
| `users` | `models/core.py::User` | 主键 `id: VARCHAR(64)`，即 Clerk `user_2xxx`（不是 UUID） |
| `interview_sessions` | `models/core.py` | 面试 session；`state` 字段记录状态机 |
| `interview_messages` | `models/core.py` | 面试消息，关联 session |
| `candidate_memory` | `models/core.py` | 候选人长期记忆 / 画像 |
| `coach_plans` | `models/core.py` | Coach 生成的改进计划 |
| `eval_*` | `models/eval.py` | 评测维度、运行、判分 |
| LangGraph checkpoint 表 | `langgraph-checkpoint-postgres` 创建 | 跨 turn / session 恢复 |

## 约束与索引

- 业务表用 PG `UUID` / `TIMESTAMP(with timezone)` / `JSONB`（详见 `models/core.py` import）
- 索引迁移命名：`<rev>_add_xxx_index.py`（参考 `2e6f7a8b9c10_add_active_interview_run_index.py`）
- 加索引前先在 explain analyze 上看实际查询；不要凭直觉

## 迁移流程

1. 改 `models/*.py`
2. `cd backend && uv run alembic revision --autogenerate -m "<short>"`
3. 人工审 autogenerate 的脚本（autogenerate **不**识别枚举重命名、约束细节）
4. `uv run alembic upgrade head` 本地试
5. 写迁移走 `migration` workflow（不是 feature）

## 关于 user_id

**陷阱**：早期代码可能假设 user_id 是 UUID。看到 `UUID` 字段类型时确认是不是 Clerk id——是的话改 `VARCHAR(64)`。
