# Testing

## 分层

| 层 | 位置 | 关键工具 | 何时跑 |
|---|---|---|---|
| 单测（后端） | `backend/tests/unit/` | pytest（asyncio_mode=auto） | 每次 PR |
| 集成（后端） | `backend/tests/integration/` | pytest + 测试 DB | 触碰数据库 / service 时 |
| 评测（后端） | `backend/tests/eval/` | `eval-cli` + dataset | LLM 行为变更时 |
| 单测（前端） | `frontend/**/*.test.{ts,tsx}` | vitest + testing-library | 每次 PR |
| 文件存在性 | `frontend/scripts/assert-login-page.mjs` | node | 重命名 / 删页面时 |

## 命令速查

```bash
# 后端
cd backend
uv run pytest tests/unit -q
uv run pytest tests/integration -q
uv run eval-cli judge --dataset <path>

# 前端
cd frontend
pnpm test
pnpm typecheck
pnpm check:files
```

## 写测试的原则

- 单测不能连 DB / 不能调 LLM；要 mock LLM 客户端
- 集成测试用 dedicated 测试 DB；fixture 负责清理
- LLM 评测用 `eval/judge.py` 给打分；**不要**在单测里 assert LLM 文本
- React 组件用 `userEvent.click`，不要直接 fire DOM event
- 避免 `await new Promise(r => setTimeout(r, ...))`——用 `findBy*` 等待

## CI 触发顺序

1. lint / typecheck（快，先 fail）
2. unit
3. integration（条件触发：修了 services/models/alembic 时跑）
4. eval（条件触发：修了 agents/prompts 时跑）

## 协议自检

`.ai/bin/lint-protocol` 校验 `.ai/workflows/*.yaml` 与 `.ai/tasks/*/status.json` 一致性；
建议在 pre-commit / CI 跑。
