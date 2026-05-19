# M1 里程碑计划：工程地基 + MVP 单 Agent 闭环

> 覆盖 Phase：**P0 + P1**
> 简历卖点：**"Agent + RAG 工程师面试系统"**
> 状态：v0.1（初版）
> 📍 全景位置：见 [`../product-vision.md` §6.5 M↔Phase↔功能模块总览图](../product-vision.md)

---

## 1. 里程碑目标

完成生产级 AI 全栈脚手架 + 第一个能跑通的单 Agent 单轮面试闭环。**不含记忆 / 不含多 Agent / 不含反思**。完成后用户能在浏览器里跟 AI 完整地走完一轮 5-10 题的面试问答。

## 2. 范围

| 包含 | 不包含（属于 M2+） |
|---|---|
| ✅ 全栈脚手架（FastAPI / Celery / Redis / pgvector / Next.js） | ❌ 多 Agent 编排 |
| ✅ Alembic 迁移流程 + 数据层 | ❌ 长期记忆 |
| ✅ 单个面试官 Agent | ❌ 复盘报告 |
| ✅ RAG 题库（3-5 个核心文档源） | ❌ Reflexion |
| ✅ SSE 流式回答 | ❌ 鉴权完整版 |
| ✅ 最简前端聊天页 | ❌ 部署到生产 |
| ✅ 工程规范（CLAUDE.md / AGENTS.md） |  |

---

## 3. P0 — 工程地基

### 3.1 仓库结构

```
multi-agent-coach/
├── CLAUDE.md                    # Claude Code 主控规范
├── AGENTS.md                    # Codex 主控规范（与 CLAUDE.md 同步）
├── README.md
├── dev.sh                       # 一键启动（混合模式）
├── docker-compose.yml           # postgres + redis + pgvector
├── docker-compose.prod.yml      # 生产版（M4 用）
├── .env.example
├── docs/
│   ├── product-vision.md
│   ├── plans/
│   ├── specs/                   # 每个功能的 spec
│   └── changelogs/
├── backend/
│   ├── pyproject.toml           # uv
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── api/                 # 路由层（不调 LLM）
│   │   │   ├── v1/
│   │   │   │   ├── interview.py
│   │   │   │   ├── rag.py
│   │   │   │   └── health.py
│   │   │   └── deps.py
│   │   ├── services/            # LLM / 业务逻辑层
│   │   │   ├── agents/          # M1: 单 Agent；M2: 多 Agent
│   │   │   ├── rag/
│   │   │   ├── memory/          # M2 开始
│   │   │   └── reflexion/       # M2 开始
│   │   ├── models/              # SQLAlchemy ORM
│   │   ├── schemas/             # Pydantic
│   │   ├── core/                # 配置 / 日志 / 异常 / SSE
│   │   ├── workers/             # Celery 任务
│   │   └── db/                  # session / pgvector helper
│   └── tests/
├── frontend/
│   ├── package.json             # pnpm
│   ├── next.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # 着陆 / 聊天页
│   │   └── api/                 # Next API routes（仅做代理）
│   ├── components/
│   │   ├── chat/
│   │   └── ui/                  # shadcn
│   └── lib/
│       └── sse.ts               # EventSource 封装
└── scripts/
    ├── seed_rag.py              # RAG 题库摄入
    └── reset_db.py
```

### 3.2 技术栈与版本

| 组件 | 版本 |
|---|---|
| Python | 3.12 |
| FastAPI | 最新稳定 |
| uvicorn | 最新稳定 |
| SQLAlchemy | 2.x（async） |
| Alembic | 最新稳定 |
| Celery | 5.x |
| Redis | 7.x（含 Pub/Sub） |
| PostgreSQL | 16 |
| pgvector | 最新稳定 |
| LangGraph | 最新（M1 只用基础 LLM 调用，M2 才用图） |
| Node | 20 LTS |
| Next.js | 16（App Router） |
| TypeScript | 5.x |
| Tailwind | 4.x |
| shadcn/ui | 最新 |

### 3.3 dev.sh 设计（混合启动）

```bash
#!/bin/bash
# 混合模式：Docker 跑 postgres + redis，其余服务直接在本机跑
docker compose up -d postgres redis
cd backend && uv run alembic upgrade head
cd backend && uv run uvicorn app.main:app --reload --port 8000 &
cd backend && uv run celery -A app.workers.celery_app worker --loglevel=info &
cd frontend && pnpm dev &
wait
```

### 3.4 数据层（最小集）

P0 阶段先建：
- `users` 表（id / email / created_at，无密码 P0 不做完整鉴权）
- `rag_chunks` 表（id / source / title / content / embedding vector(1536) / metadata jsonb）

### 3.5 鉴权 stub

P0：固定使用 `user_id=1` 的本地用户，不做注册/登录。
M2 / M4 再做完整鉴权。

### 3.6 日志 / 错误处理 / 健康检查

- 结构化日志（`structlog`）
- 全局异常处理器（FastAPI exception_handler）
- `/api/v1/health` 检查 DB + Redis 连通

### 3.7 配置管理

- 严格用环境变量；禁止硬编码 Key
- `.env.example` 必须维护
- 后端用 `pydantic-settings`

### 3.8 工程规范（CLAUDE.md / AGENTS.md）

参考 `job-intel-agent` / `offer-copilot` 的 10 条全局约束 + Skill 路由表，复制并裁剪适配。**不复用业务代码，只复用规范模板**。

### 3.9 P0 验收标准

- [ ] `./dev.sh` 一键起服务，访问 http://localhost:3000 看到首页
- [ ] `http://localhost:8000/api/v1/health` 返回 `{"status": "ok"}`
- [ ] Alembic `upgrade head` 成功，`users` + `rag_chunks` 建表
- [ ] 日志结构化输出到 stdout

---

## 4. P1 — MVP 单 Agent 闭环

### 4.1 单个面试官 Agent 设计

最简版本，**一个 Agent 承担所有角色**：
- 输入：`user_message`、`session_id`、`current_question_idx`
- 流程：
  1. 检查是否首次提问 → 是则从 RAG 题库随机抽题
  2. 用户回答后，给一句话点评（不展开评分，那是 M2 的 Reflexion）
  3. 抽下一题，直到 5-10 题为止
- 输出：流式 SSE 推送

Prompt 简化模板：
```
你是 AI Agent 工程师的面试官。当前在面试关于 {topic} 的题目。
本场已答 {n}/{total} 题。
请基于上一题用户的回答给一句话点评，然后出下一题。
```

### 4.2 RAG 题库（3-5 个核心文档源）

P1 必抓的 5 个源：
1. **LangGraph 官方文档**（核心 API + Multi-Agent）
2. **Mem0 README + Architecture**
3. **Reflexion 论文摘要 + 关键章节**
4. **MemGPT 论文摘要 + 关键章节**
5. **Anthropic MCP 文档（Quickstart）**

摄入流水线：
- Firecrawl 抓取 → chunk（500-800 token，overlap 100）→ OpenAI `text-embedding-3-small` → 入 `rag_chunks`
- 单独 Celery 任务，可重跑
- 检索：cosine 相似度 top-K=5，可选 rerank（P1 不做 rerank）

### 4.3 单轮问答流程

```
[POST /api/v1/interview/start]
  └─→ 创建 interview_session（M1 这张表可以最简：id / user_id / created_at）

[POST /api/v1/interview/{session_id}/answer]  body: {message}
  └─→ 调 面试官 Agent → 流式 SSE 推回
```

### 4.4 SSE 流式

后端：
- `EventSourceResponse`（sse-starlette）
- LLM 流式 token → `event: token` 推送
- 完成时 `event: done`

前端：
- `EventSource` 客户端，token 累加渲染
- 错误重连（最多 3 次）

### 4.5 最简前端聊天页

- 1 个页面 `/`
- 顶部按钮"开始面试"
- 聊天气泡（用户 / AI）
- 输入框 + 发送
- shadcn `<Card>` `<Button>` `<Textarea>`

### 4.6 P1 验收标准

- [ ] RAG 题库摄入完成，`scripts/seed_rag.py` 跑通，库内有 >100 个 chunks
- [ ] 浏览器能开始一场面试，AI 出题，用户回答，AI 点评 + 出下一题，跑完 5 题
- [ ] SSE 流式正常（看到 token 一个个出现）
- [ ] 后台日志能看到完整链路

---

## 5. 工期粗估（不强制约束，参考）

| Phase | 名义工时 |
|---|---|
| P0 | 16-20h |
| P1 | 20-24h |
| **小计 M1** | **36-44h** |

## 6. 简历兑现点（M1 完成后能写什么）

简历项目栏（80 字）：
> 设计实现 AI Agent 工程师面试问答系统。FastAPI + LangGraph + pgvector 全栈架构，RAG 题库基于官方文档与论文构建，SSE 流式问答。

招聘官能 get 的点：
- 全栈能力（前后端 + DB + 流式）
- AI 工程基本功（RAG / embedding / 向量检索）

**但 M1 还不够进面试官记忆点**，必须做到 M2 才有强叙事。

## 7. 关键风险

| 风险 | 应对 |
|---|---|
| 抓取的 5 个源质量不一 | 优先抓 LangGraph / Mem0 / Anthropic 三个，论文用 arxiv html 版 |
| SSE + Next.js 联调问题 | 用 `sse-starlette` + 浏览器原生 `EventSource`，避开 fetch streaming 坑 |
| pgvector 索引建错 | 用 IVFFlat，lists=100 起步 |
