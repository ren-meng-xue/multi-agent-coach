# 7 天求职 Ship 计划（从 P0-P4 抽取的求职兑现切片）

> 状态：v0.2（+ Clerk 多用户鉴权）
> 目标：**7 天 × ~9.2h = 64h 名义工时，ship 出可投简历的版本**
> 兑现里程碑：**M2 节点**（有记忆的多 Agent + 自反思 + 多用户鉴权）

---

## 0. 产品全景中的位置

本文档是「9 Phase 完整路线」中的 **7 天 ship 切片**，覆盖：

```
  全产品 9 Phase 路线（详见 ../product-vision.md §7）：
    P0 工程地基 → P1 单 Agent MVP → P2 多 Agent 顺序 →
    P3 分级长期记忆 → P4 Reflexion → P5 Eval → P6 高级协作 →
    P7 Meta-cognition → P8 生态&多模态 → P9 商业化

  本 7 天 ship 计划覆盖：
    [P0 ★ 全部] [P1 ★ 全部] [P2 ★ 全部] [P3 简化版] [P4 简化版]
                                                  ──→ 兑现 M2 里程碑
```

对应简历里程碑：**M2 — 有记忆的多 Agent + 自反思**（核心叙事兑现节点）。

完整的 9 Phase 拆分表 / Phase 依赖关系图 / 关键依赖说明 / 4 大里程碑跃迁节点详见：
- [`../product-vision.md`](../product-vision.md) §6 简历里程碑视角
- [`../product-vision.md`](../product-vision.md) §7 9 Phase 完整拆分与依赖关系

未覆盖 Phase 的详细计划见：
- [`m1-foundation.md`](./m1-foundation.md) — P0 + P1 详细计划（本文档技术细节的扩展版）
- [`m2-core.md`](./m2-core.md) — P2 + P3 + P4 完整版（本文档抽取自此）
- [`m3-engineering.md`](./m3-engineering.md) — P5 + P6 + P7（M2 后续升级）
- [`m4-saas.md`](./m4-saas.md) — P8 + P9（终态商业化）

---

## 1. 目标 & 兑现承诺

7 天后产出：
- ✅ 可在本地 docker-compose 跑通的完整产品
- ✅ 浏览器端能跨会话感受到"AI 越用越懂我"
- ✅ 一场面试完成后有完整复盘报告（评分 + 改进 + STAR + 弱点）
- ✅ 3 分钟 Demo 视频
- ✅ README + 架构图
- ✅ GitHub 公开仓库
- ✅ 简历项目栏可填（120 字版本）

## 2. 范围抽取

### 2.1 从 P0-P4 抽取的部分

| 大计划 Phase | 7 天版抽取 |
|---|---|
| **P0 工程地基** | 全部（含 Clerk 多用户鉴权集成——Email + GitHub OAuth + JWT 校验） |
| **P2 多 Agent 顺序** | 3 Agent（HR / 技术 / Coach）+ LangGraph 编排（顺序流转，不做 conditional） |
| **P3 分级长期记忆** | L0（state）+ L2（user_profile）+ L3（star_stories）+ L4 简化版（weakness_tags） |
| **P4 Reflexion** | 单轮（评分 + 反思 + 改进 + 弱点回写），**不做反向出题闭环** |

### 2.2 砍掉的部分（明确写出来）

| 砍掉 | 归属里程碑 |
|---|---|
| L1 工作记忆独立（合并进 L2 history JSON） | M2 完整版后续补 |
| L5 反思日志 / Meta-reflection | M3 |
| L4 知识图谱 / Neo4j | M3 |
| 共享 scratchpad / 动态路由 / HITL / A2A | M3 |
| BOSS 终面 / 记忆管家 / 出题升级 Agent | M3 |
| LLM-as-Judge 多 Judge + Benchmark | M3 |
| 量化进步曲线 / 仪表盘 | M3 |
| ~~多用户 / 鉴权~~ | ~~M4~~ **V1 已提前实现（Clerk）** |
| Stripe 付费 | M4 |
| MCP / Voice / 移动端 | M4 |
| LangSmith / Sentry / 监控 | M4 |
| CI/CD / 生产部署 | M4 |
| 反向出题闭环（基于弱点） | M2 完整版（7 天后续补） |

## 3. 技术栈与版本（固定，不动）

| 组件 | 版本 |
|---|---|
| Python | 3.12 |
| FastAPI / uvicorn | 最新稳定 |
| SQLAlchemy 2.x async | |
| Alembic | |
| Celery 5.x | |
| Redis 7 | |
| PostgreSQL 16 + pgvector | |
| LangGraph | 最新（用 `context7` 拉文档确认 API） |
| OpenAI Python SDK | gpt-4o / gpt-4o-mini |
| Next.js 16 + TS + Tailwind + shadcn | |
| pnpm / uv | |
| Firecrawl | 抓题库源 |
| **@clerk/nextjs + pyjwt[crypto]** | **多用户鉴权（Clerk JWT）** |
| sse-starlette | SSE 流式 |
| pytest + pytest-asyncio + httpx | |

## 4. 仓库结构（同 m1-foundation.md）

参考 `docs/plans/m1-foundation.md` 第 3.1 节。

## 5. 数据模型（7 张表完整字段）

```sql
-- 1. 用户（Clerk user_id = VARCHAR 主键）
CREATE TABLE users (
  id VARCHAR(64) PRIMARY KEY,    -- Clerk user_id，格式 "user_2abc..."
  email VARCHAR(255) UNIQUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 2. RAG 题库
CREATE TABLE rag_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source VARCHAR(100),              -- "langgraph" / "mem0" / ...
  title TEXT,
  content TEXT,
  embedding vector(1536),
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX rag_chunks_embedding_idx ON rag_chunks USING ivfflat (embedding) WITH (lists = 100);

-- 3. 长期画像（L2）
CREATE TABLE user_profile (
  user_id INT PRIMARY KEY REFERENCES users(id),
  goals TEXT,
  experience_summary TEXT,
  tech_strengths JSONB DEFAULT '{}',
  tech_weaknesses JSONB DEFAULT '{}',
  soft_strengths JSONB DEFAULT '{}',
  star_completeness_score FLOAT DEFAULT 0,
  total_interviews INT DEFAULT 0,
  history JSONB DEFAULT '[]',       -- 简化版 L1：把每场摘要塞进 history 数组
  profile_embedding vector(1536),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 4. 面试场次
CREATE TABLE interview_session (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id INT REFERENCES users(id),
  started_at TIMESTAMP DEFAULT NOW(),
  ended_at TIMESTAMP,
  summary TEXT,
  scores JSONB,
  phase_completed JSONB
);

-- 5. 面试消息
CREATE TABLE interview_message (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES interview_session(id),
  role VARCHAR(20),                 -- user / hr_agent / tech_agent / coach
  content TEXT,
  retrieved_context JSONB,
  reflexion_payload JSONB,          -- P4 写入
  created_at TIMESTAMP DEFAULT NOW()
);

-- 6. STAR 故事库（L3）
CREATE TABLE star_stories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id INT REFERENCES users(id),
  project_name VARCHAR(255),
  situation TEXT,
  task TEXT,
  action TEXT,
  result TEXT,
  quantified_results TEXT,
  tech_stack JSONB,
  quality_score FLOAT,
  source_message_id UUID REFERENCES interview_message(id),
  embedding vector(1536),
  created_at TIMESTAMP DEFAULT NOW()
);

-- 7. 弱点标签（L4 简化版）
CREATE TABLE weakness_tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id INT REFERENCES users(id),
  tag VARCHAR(100),
  category VARCHAR(50),
  severity FLOAT,
  occurrence_count INT DEFAULT 1,
  last_occurred_session UUID,
  related_message_ids JSONB,
  status VARCHAR(20) DEFAULT 'active',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

## 6. API 设计（关键接口）

```
GET  /api/v1/health
POST /api/v1/interview/start            -> {session_id, first_question}
POST /api/v1/interview/{sid}/answer     -> SSE: token stream + final reflexion
GET  /api/v1/interview/{sid}/report     -> 复盘报告 JSON
GET  /api/v1/profile/me                 -> L2 user_profile
GET  /api/v1/stars/me                   -> L3 列表
GET  /api/v1/weaknesses/me              -> L4 列表
POST /api/v1/rag/seed                   -> 触发 Celery 摄入任务（dev only）
```

## 7. LangGraph 节点设计（7 天版）

```
START → hr_agent → tech_agent → reflexion → memory_writer → coach_agent → END
```

- `hr_agent`: 出 2-3 题行为面
- `tech_agent`: 出 3-4 题技术面，每题后接 reflexion
- `reflexion`: 评分 + 反思 + 改进建议（结构化输出）
- `memory_writer`: Celery 异步写 L2/L3/L4
- `coach_agent`: 综合复盘

详见 `m2-core.md` 第 3 节。

## 8. 分级记忆设计（7 天版简化）

详见 `m2-core.md` 第 4 节，但 7 天版砍：
- L1 工作记忆合并到 `user_profile.history` JSONB 数组（保留最近 10 场摘要）
- L4 用简单 `weakness_tags` 表，无知识图谱

## 9. Reflexion 设计（7 天版）

详见 `m2-core.md` 第 5 节。7 天版砍：
- 不做反向出题闭环（弱点只写入，不自动驱动下一题）
- JSON Schema 用 Pydantic + OpenAI Function Call 强约束

## 10. 前端页面设计（2 页面 wireframe）

### 10.1 页面 1：面试房间 `/interview/[session_id]`

```
┌─────────────────────────────────────────────────────┐
│ Multi Agent Coach            [当前阶段：技术面 3/8]     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [HR Agent 头像] "你好，请简单介绍一下..."          │
│                                                     │
│  [You]           "我做过 LangGraph ..."             │
│                                                     │
│  [HR Agent]      "听起来很有意思，..." [流式]       │
│                                                     │
│  ────── 切换到 技术面 ──────                        │
│                                                     │
│  [Tech Agent]    "我看你提到了 LangGraph，..."      │
│                                                     │
├─────────────────────────────────────────────────────┤
│  [输入你的回答...]                       [发送 →]   │
└─────────────────────────────────────────────────────┘
        [💡 复盘抽屉]  <- 右下浮动按钮，点击展开 <Sheet>
```

抽屉内容（折叠面板）：
- 评分（实时雷达图，每题 reflexion 后更新）
- STAR 故事库（本场抽出的 + 历史的）
- 弱点标签（active 列表）

### 10.2 页面 2：复盘报告 `/report/[session_id]`

```
┌──────────────────────────────────────────────────────┐
│ ← 返回                                                │
│                                                       │
│ 本场复盘 · 2026-05-25 14:30 - 15:12 (42 min)         │
├──────────────────────────────────────────────────────┤
│ 总评                                                  │
│   "本场整体表现不错，但 STAR 完整度需提升..."         │
│                                                       │
├──────────────────────────────────────────────────────┤
│ 评分 [雷达图]                                         │
│   clarity 7.5 │ depth 6.2 │ specificity 5.8         │
│   STAR_completeness 4.5  ← 弱点                      │
├──────────────────────────────────────────────────────┤
│ 关键改进建议（来自 Reflexion）                        │
│  ・讲项目时缺少量化结果（出现 3 次）                 │
│  ・系统设计深度不够，建议补 trade-off 视角           │
├──────────────────────────────────────────────────────┤
│ 新增 STAR 故事 (2)                                    │
│  ・LangGraph 多步调研 Agent ─[查看详情]             │
│  ・RAG citation guard 系统  ─[查看详情]             │
├──────────────────────────────────────────────────────┤
│ 新增 / 强化的弱点标签                                 │
│  ・star-缺量化（severity 0.7，已出现 3 次）          │
│  ・系统设计-trade-off（severity 0.5）                │
└──────────────────────────────────────────────────────┘
```

---

## 11. Day-by-Day 详细任务清单

### Day 1（10h）：脚手架 + 数据层 + Clerk 接入

| 任务 | 工时 | 验证 |
|---|---|---|
| 初始化 `multi-agent-coach/` 仓库 + git init | 0.5h | `git status` 干净 |
| `backend/pyproject.toml` + `uv init` + 装依赖 | 0.5h | `uv sync` 成功 |
| `frontend/` Next.js 16 init + Tailwind + shadcn | 1h | `pnpm dev` 起来 |
| `docker-compose.yml`（postgres + redis + pgvector） | 0.5h | `docker compose up -d` 起来 |
| `dev.sh` 一键启动脚本 | 0.5h | `./dev.sh` 跑通 |
| Alembic init + 7 张表 schema + 首次迁移 | 2h | `alembic upgrade head` 成功 |
| SQLAlchemy 模型（7 张表对应）| 1.5h | 单元测试能 CRUD |
| FastAPI 主入口 + `/health` + 异常处理 + 结构化日志 | 1h | `curl /health` 返回 ok |
| `.env.example` + `pydantic-settings` 配置 | 0.5h | 启动时校验通过 |
| **D1 EOD commit** | - | "feat: 工程脚手架 + 数据层" |

**风险点**：pgvector 扩展安装 / Alembic + async 引擎兼容

### Day 2（8h）：RAG 题库 + LangGraph 骨架

| 任务 | 工时 | 验证 |
|---|---|---|
| `scripts/seed_rag.py` 摄入流水线骨架 | 1h | 命令行能跑 |
| Firecrawl 配置 + 抓 5 个文档源（LangGraph / Mem0 / Reflexion 论文 / MemGPT 论文 / MCP 文档） | 2.5h | `rag_chunks` 表 > 100 条 |
| chunk 切分（500-800 token，overlap 100）+ OpenAI embedding | 1h | 抽样验证 chunk 质量 |
| pgvector 检索 helper `search_rag(query, top_k)` | 1h | 命令行能检索 |
| LangGraph `StateGraph` 骨架 + `InterviewState` TypedDict | 1.5h | 空节点能跑通 START → END |
| LangGraph 节点占位 + 边定义 | 1h | 编译 graph 无错 |
| **D2 EOD commit** | - | "feat: RAG 摄入 + LangGraph 骨架" |

**风险点**：Firecrawl 抓取速率 / 论文 PDF 处理

### Day 3（10h）：3 Agent + SSE 流式 + JWT 鉴权

| 任务 | 工时 | 验证 |
|---|---|---|
| HR Agent 节点实现（system prompt + LLM 调用） | 1.5h | 命令行能出题 |
| 技术 Agent 节点（接 RAG 检索） | 2h | 能基于检索结果出题 |
| Coach Agent 节点 | 1h | 能输出综合复盘 |
| LangGraph `astream_events` 接 SSE | 2h | token 一个个推到客户端 |
| `POST /api/v1/interview/start` + `POST /answer` 接通 | 1h | curl SSE 能看到流式 |
| 前端简陋聊天 UI（一个输入框 + 消息列表）+ SSE 客户端 | 0.5h | 浏览器能看到 token 流式 |
| **D3 EOD commit** | - | "feat: 3 Agent + SSE 流式" |

**里程碑**：浏览器能完整跑完一次"无记忆假面试"

**风险点**：LangGraph `astream_events` v1 vs v2 API 差异 / SSE Next.js 跨域

### Day 4（8h）：分级记忆 L0 + L2 + 读策略

| 任务 | 工时 | 验证 |
|---|---|---|
| L0 短期：LangGraph state messages 维护正常 | 0.5h | state 序列化测试 |
| L2 长期画像 CRUD 函数（get / upsert / update_ema） | 1.5h | pytest 单测通过 |
| L2 画像增量更新策略（EMA α=0.3） | 1h | 模拟 3 次更新数值正确 |
| `load_memory(user_id, topic)` helper（注入到每个 Agent） | 1.5h | 测试输出结构 |
| 修改 3 个 Agent 节点：开场注入 L2 画像 | 2h | 浏览器：第 2 次面试 HR Agent 能引用上次内容 |
| `GET /api/v1/profile/me` 接口 | 0.5h | curl 拿到画像 |
| Celery worker 启动 + Celery 异步任务骨架 | 1h | Celery 队列能收到任务 |
| **D4 EOD commit** | - | "feat: 分级记忆 L0+L2 + 读策略" |

**里程碑**：第 2 次开面试能感受到 Agent 记得上次

**风险点**：跨会话数据是否真的写到 L2 + 读取顺序

### Day 5（8h）：L3 STAR + L4 弱点 + Reflexion

| 任务 | 工时 | 验证 |
|---|---|---|
| L3 STAR 抽取函数（LLM Function Call 输出结构化） | 2h | 抽 5 个测试样本结构正确 |
| L3 入库 + 同项目去重（embedding 相似度 > 0.85） | 1h | 重复入库测试 |
| L4 弱点判定逻辑 + 写入 weakness_tags | 1h | 低分维度能正确打标 |
| Reflexion Agent 节点（Function Call JSON 输出） | 2h | JSON 结构稳定，Pydantic 校验通过 |
| Reflexion 写回链路：→ L2 EMA / → L4 / → interview_message.reflexion_payload | 1.5h | 一题答完后能看到全部写入 |
| 整链路联调（双场连环测试用例） | 0.5h | pytest 集成测试通过 |
| **D5 EOD commit** | - | "feat: L3 STAR + L4 弱点 + Reflexion 单轮" |

**里程碑**：完整 M2 后端链路打通

**风险点**：Reflexion JSON 结构不稳定 → 用强 Pydantic schema + 失败重试 3 次

### Day 6（11h）：前端 2 页面 + Clerk 登录 + 联调

| 任务 | 工时 | 验证 |
|---|---|---|
| 面试房间页布局（Next.js + shadcn） | 1.5h | 静态页能看 |
| SSE 客户端 hook（`useEventSource`） | 1h | token 流式渲染 |
| 顶部进度条 + Agent 角色切换动画 | 1h | 视觉清晰 |
| `<Sheet>` 抽屉：实时复盘（评分 / STAR / 弱点 3 个折叠面板） | 2h | 能展开查看 |
| 复盘报告页（雷达图 + 改进建议列表 + STAR 卡片 + 弱点标签） | 2h | 完整渲染 |
| 整体浏览器联调（黄金路径） | 0.5h | 能跑通完整一场面试 |
| **D6 EOD commit** | - | "feat: 前端面试房间 + 复盘报告页" |

**里程碑**：可在浏览器完整 demo

**风险点**：recharts / @nivo 雷达图 vs 自己用 Canvas / shadcn `<Chart>` 决定 → 用 shadcn 自带 Chart 最快

### Day 7（9h）：测试 + 部署 + Demo + 简历素材

| 任务 | 工时 | 验证 |
|---|---|---|
| 关键路径 pytest 集成测试（3 个 case：单场面试 / 双场连环 / Reflexion 结构稳定性） | 2h | `pytest` 全绿 |
| bug 修复轮（预留时间） | 1.5h | 黄金路径无 P0 |
| `docker-compose.prod.yml` + 本地生产模式跑通 | 1h | `./dev.sh prod` 启动 |
| README（含架构图 + 截图 + 快速开始） | 1h | GitHub README 可读 |
| 录 Demo 视频（3 分钟脚本：开场 → 第 1 场面试 → 第 2 场跨会话记忆生效 → 复盘报告） | 1.5h | 视频可分享 |
| 简历素材整理（架构图 SVG / 截图 PNG / 项目栏文案 120 字） | 1h | 可粘到简历 |
| 最终 commit + push 到 GitHub + 公开仓库 | - | URL 可访问 |
| **D7 EOD：可投简历** | - | 🎉 |

**里程碑**：M2 兑现完成，简历可投

---

## 12. 验收标准（7 天 ship 完成判定）

必须全部满足：

- [ ] `./dev.sh` 一键启动 5 个服务（postgres / redis / backend / celery / frontend）
- [ ] 数据库 7 张表正确建立，Alembic 迁移可重放
- [ ] RAG 题库 ≥ 100 chunks，能向量检索
- [ ] LangGraph 3 Agent（HR / 技术 / Coach）顺序流转无错
- [ ] SSE 流式回答正常（前端能看到 token 流）
- [ ] Reflexion 输出结构化 JSON（评分 + 改进 + 追问 + 弱点）
- [ ] 一场面试结束后：L2 / L3 / L4 都有数据
- [ ] 第二场面试开场，HR Agent 能引用第一场提到的项目
- [ ] 复盘报告页能完整展示评分 / 建议 / STAR / 弱点
- [ ] pytest 集成测试 ≥ 3 个 case 全绿
- [ ] README + 3 分钟 Demo 视频
- [ ] GitHub 仓库公开
- [ ] 简历项目栏文案准备好

## 13. 简历素材清单

D7 必须产出：

| 素材 | 用途 |
|---|---|
| 项目栏文案（120 字 + 50 字短版） | 简历正文 |
| 架构图 SVG | 项目主页 + LinkedIn |
| 3-5 张产品截图 | 简历附件 / 项目主页 |
| 3 分钟 Demo 视频（YouTube unlisted） | 简历 + 投递信附 URL |
| GitHub README（架构 + 快速开始 + 技术亮点） | 招聘官点 GitHub 第一眼看的 |
| 1-2 个技术深度博客（可选，M2 完成后再写） | 加分项 |

## 14. 关键决策点（每天可能要做的决策）

- D2：抓哪 5 个 RAG 源？（默认 LangGraph / Mem0 / Reflexion 论文 / MemGPT 论文 / MCP 文档）
- D3：技术 Agent 的 topic 怎么定？固定还是动态？（建议固定 3 个 topic：LangGraph / RAG / Eval）
- D4：L2 画像的 `tech_strengths` schema 怎么定？（建议从 RAG 文档源提取的 ~15 个标签）
- D5：Reflexion 4 维度评分用 gpt-4o 还是 gpt-4o-mini？（建议 gpt-4o，成本可控）
- D6：图表用 shadcn `<Chart>` 还是 recharts？（建议 shadcn，快）
- D7：Demo 视频要不要剪辑？（建议 OBS 录屏 + Descript 简单剪辑，1h 内搞定）

---

## 15. 如果遇到延期怎么办

最先砍的（按砍掉影响降序）：
1. D7 部分测试用例 → 只保留 1 个核心 case
2. D6 复盘报告页的雷达图 → 用简单数字列表代替
3. D5 STAR 同项目去重 → 暂时允许重复
4. D2 RAG 源砍到 3 个（LangGraph / Mem0 / Reflexion）

绝对不能砍的（砍了 M2 故事就崩）：
- 3 Agent 顺序流转
- L2 画像跨会话生效
- Reflexion 评分 + 写回 L4
- 复盘报告页（哪怕只是文本版）
- Demo 视频

---

## 16. D0（启动日）准备清单

执行 D1 前需要确认：
- [ ] OpenAI API Key 准备好（gpt-4o + embedding）
- [ ] Firecrawl API Key
- [ ] GitHub 仓库名定好（建议：`multi-agent-coach` 或 `multi-agent-coach-ai`）
- [ ] 是否要公开仓库（建议从 D1 起就公开，吸 Star）
- [ ] 本机 Docker / Postgres / Redis 都能跑
- [ ] Node 20 LTS + pnpm + Python 3.12 + uv 都装好
