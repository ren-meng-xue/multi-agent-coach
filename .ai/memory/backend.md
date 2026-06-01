# Backend Conventions

## 运行

```bash
cd backend
uv sync                     # 安装依赖
uv run uvicorn app.main:app --reload --port 8000
uv run celery -A app.workers worker --loglevel=info   # 异步任务
```

`./dev.sh` 在仓库根启动全栈（PG/Redis/后端/Celery/前端），日志写到 `backend.log` / `celery.log` / `frontend.log`。

## 模块边界

- **api/v1/**：只写参数校验、调用 service、包装响应；不写业务逻辑、不写 SQL
- **services/**：业务编排，可调多个 service / agent；事务边界在这里
- **agents/**：LangGraph 图与节点；不直接读写数据库（数据用 service 注入 state）
- **models/**：纯 ORM，不写查询；查询封装到 service 或 repository（项目里 service 兼任）
- **eval/**：可独立运行的评测；和主链路解耦，避免引用 services 内的 LLM 调用包装

## LangGraph 约定

- 每个 agent 一个目录：`graph.py` / `nodes.py` / `prompts.py` / `state.py`
- State 用 TypedDict / Annotated；不要塞大 blob（checkpoint 会膨胀）
- prompt 单独放 `prompts.py`；模板用 f-string 或 LangChain `PromptTemplate`
- 长会话用 `langgraph-checkpoint-postgres`；启动时调 `setup_*_checkpointer`

## 错误处理

- 业务错误：raise `AppException`，由全局 handler 翻译成 `Response`
- 系统错误（DB 连接、LLM 超时）：让其自然冒泡 + structlog 记录；不要吞
- 重试用 `tenacity`，已是 dep；只对幂等操作重试

## 配置

`core/config.Settings` 是唯一配置源（Pydantic BaseSettings），从 `.env` / 环境变量读。不要在模块顶层 `os.environ.get(...)`。

## 测试

- `backend/tests/unit/`：纯函数 / 节点逻辑，不连 DB
- `backend/tests/integration/`：连测试 DB / 真实 service
- `backend/tests/eval/`：评测离线跑
- 全部 pytest，async 用 `pytest-asyncio`（mode=auto，已配）
