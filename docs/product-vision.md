# Multi Agent Coach — 产品愿景文档

> 文档类型：Product Vision / PRD
> 状态：v0.2（补 9 Phase 详细拆分 + 依赖图 + 4 跃迁节点）
> 最后更新：2026-05-18

---

## 1. 一句话产品定义

**Multi Agent Coach**（项目代号：`multi-agent-coach`）是面向 AI Agent / 全栈 AI 工程师候选人的「面试陪练 + 长期记忆数字分身」。多个角色 Agent 协作模拟真实多轮面试，分级长期记忆跨会话记住你的成长曲线、STAR 故事库、答题盲点，Reflexion 让 Agent 看完答题后自我反思打分并针对性反向出题。

## 2. 目标用户

| Persona | 画像 | 核心痛点 | Multi Agent Coach 的解 |
|---|---|---|---|
| **P1：AI 应用工程师求职者** | 工作 2-5 年，转 AI Agent 方向 | LangGraph / RAG / Eval 这类题题型新，市面陪练工具都不专业 | 垂直题库 + 多 Agent 模拟全流程 |
| **P2：全栈 AI 独立开发者** | 想找 AI 创业公司或独立开发岗 | 缺真实面试演练；自己讲项目时总抓不到亮点 | STAR 故事库 + Coach 复盘把项目讲透 |
| **P3：产品本身的作者（自用）** | 即将投简历 | 每天高强度面试演练 + 持续追踪自己弱点 | 数据飞轮：用得越多越准 |

## 3. 一句话价值主张

> **"不是泛泛的 AI 面试官，而是一个会成长、会反思、会针对性出题的多 Agent 陪练系统。它跨会话记住你的每一次答题，3 周后能告诉你‘你讲项目时永远讲不清量化结果’。"**

## 4. 典型用户故事

### Story 1：跨会话记忆生效
小张第 1 次面试，向 HR Agent 介绍自己做过 LangGraph 项目；
第 2 次面试，技术 Agent 直接说"上次你提到 LangGraph 项目，我们今天深入聊聊里面的状态管理"。

### Story 2：弱点驱动出题
小李连续 2 场被技术 Agent 问"系统设计-高并发"答得不好；
第 3 场出题 Agent 自动出"如何为 10 万 QPS 的 LLM 服务设计限流"，并提醒"这是你的反复盲点"。

### Story 3：复盘可量化
小王面完一场后，复盘页显示"clarity 7/10，但 STAR_completeness 只有 4/10，建议补量化结果"。
4 周后仪表盘显示"STAR_completeness 从 4 提升到 8，进步显著"。

## 5. 完整产品形态（11 大功能模块）

### 5.1 用户层
- 多用户系统（注册 / 登录 / 订阅）
- Web App（Next.js）+ Mobile 响应式
- Voice 模式（Realtime API）
- 个人成长仪表盘

### 5.2 Agent 团队（终态 8 个 Agent）
| Agent | 职责 |
|---|---|
| 出题 Agent | 基于 JD + 用户弱点反向出题 |
| HR 面 Agent | 行为面 / STAR 引导 |
| 技术 Agent | 技术深挖 / 系统设计 |
| BOSS 终面 Agent | 高管面 + 反问环节 |
| Reflexion Agent | 评分 + 自反思 |
| Coach 复盘 Agent | 多场综合复盘 |
| 记忆管家 Agent | 自动整理 / 冲突解决 / 压缩归档 |
| 出题升级 Agent | 基于历史轨迹动态难度调整 |

### 5.3 多 Agent 协作模式
- 顺序流转（基础）
- 共享 scratchpad（协作版）
- 动态路由（根据用户表现切换 Agent）
- A2A 通信协议（最终态）
- Human-in-the-Loop（用户中途打断 / 要求换问题）

### 5.4 分级长期记忆系统（终态 6 层）
| 层级 | 内容 | 存储 |
|---|---|---|
| L0 短期 | 当前会话上下文 | LangGraph state |
| L1 工作记忆 | 本场面试摘要 | PG `interview_session.summary` |
| L2 长期画像 | 结构化能力 / 偏好 / 目标 + 向量摘要 | PG `user_profile` |
| L3 STAR 故事库 | 项目经历结构化抽取 | PG `star_stories` + pgvector |
| L4 弱点知识图谱 | Neo4j + 可视化关联 | Neo4j |
| L5 反思日志 | Reflexion 历史轨迹 + Meta-reflection | PG `reflection_logs` |

记忆特性：自动遗忘衰减 / 冲突解决 / 压缩归档 / 跨用户匿名学习

### 5.5 Reflexion 自我改进
- 单轮反思（评分 + 反思 + 改进建议）
- Meta-reflection（多场轨迹元反思）
- 闭环反向出题（反思结果驱动下一题）
- 反思质量评测

### 5.6 RAG 题库
- 终态 20+ 文档源：LangGraph / Mem0 / MCP 官方文档 + Reflexion / MemGPT 论文 + Anthropic Eval Cookbook + 真实公司面经 + 系统设计题库 + Leetcode
- 用户贡献机制 + 题库飞轮

### 5.7 Eval 评测体系
- LLM-as-Judge 多维度评分（clarity / depth / specificity / STAR_completeness）
- 量化进步曲线
- 公开 Benchmark 数据集
- 跟人类专家评分对齐实验

### 5.8 MCP Server 化
- 暴露工具：`start_interview` / `get_user_growth` / `add_star_story` / `query_weakness` / `mock_phone_screen`
- 让 Claude Code / Cursor 直接调用「帮我安排一次面试」

### 5.9 Voice 模式
- Realtime API 主链路 / Whisper + TTS fallback
- 中英文双语

### 5.10 工程化 / 可观测
- LangSmith / Langfuse 全链路追踪
- 自动化 CI/CD（GitHub Actions）
- 监控告警（Sentry + Prometheus）
- 用户行为分析（PostHog）

### 5.11 商业化
- Free / Pro / Enterprise 三层
- 按面试场次计费
- 企业版反向用：招聘方做候选人初筛

---

## 6. 简历里程碑视角（4 个跃迁节点）

整个产品的演进按「招聘官能 get 到的故事」分为 4 大里程碑。每个里程碑都是简历可独立兑现的节点。

| 里程碑 | 覆盖 Phase | 用户价值跃迁 | 简历卖点 | 文档 |
|---|---|---|---|---|
| **M1：AI 面试问答原型** | P0 + P1 | "我能跟 AI 面 Agent 工程师题" | "Agent + RAG 工程师面试系统" | `plans/m1-foundation.md` |
| **M2：有记忆的多 Agent + 自反思**（核心叙事） | P2 + P3 + P4 | "AI 越用越懂我，跨会话记得我项目经历和弱点；会给我打分、提改进建议、出针对性弱点题" | "MemGPT 分级记忆 + Reflexion 多 Agent 系统" | `plans/m2-core.md` |
| **M3：工程化 AI 产品** | P5 + P6 + P7 | "我能看到自己每周进步多少；Agent 间真协作能根据我的状态自动调整；AI 知道我反复错的盲区" | "LLM-as-Judge Eval + 高级多 Agent 协作 + Meta-cognition 知识图谱" | `plans/m3-engineering.md` |
| **M4：商业化 SaaS** | P8 + P9 | "我能在 Claude Code 里直接调起面试 / 语音陪练；对外可售卖 SaaS" | "MCP + Voice + 多用户 SaaS + 企业版" | `plans/m4-saas.md` |

**关键节点定位**：
- **M2 = 简历兑现下限**：7 天 ship 版的目标节点，120 字版简历项目栏可填
- **M3 = 工程深度兑现**：让招聘官认为"这不是 toy 项目，是真工程化"
- **M4 = 独立开发者天花板**：罕见的"端到端跑完整 SaaS"故事

---

## 6.5 M ↔ Phase ↔ 功能模块 总览图

整个产品的三层映射一图看明白：**4 大里程碑**（招聘官视角）↔ **9 Phase**（工程交付节奏）↔ **11 功能模块**（§5 完整产品形态）。

### 6.5.1 三层映射图

```
┌──────────────┐    ┌──────────────────┐    ┌─────────────────────────────────────────────┐
│ 4 大里程碑    │    │ 9 Phase          │    │ 11 功能模块（§5）                            │
└──────────────┘    └──────────────────┘    └─────────────────────────────────────────────┘

┌─────────┐
│  M1     │  ──┬── P0 工程地基             ─── （内部地基，无直接用户价值）
│ 原型    │    │
└─────────┘    └── P1 单 Agent MVP         ─── 5.1 用户层（聊天 UI 雏形）
                                               + 5.2 Agent 团队（1/8）
                                               + 5.6 RAG 题库（雏形 3-5 源）

┌─────────┐
│  M2 ★   │  ──┬── P2 多 Agent 顺序        ─── 5.2 Agent 团队（3/8）
│ 核心    │    │                               + 5.3 协作模式（顺序流转）
│ 叙事    │    ├── P3 分级长期记忆         ─── 5.4 记忆系统（L0-L4 简化版）
│         │    │                               + 5.10 工程化（异步写入）
│ 7天目标 │    └── P4 Reflexion 自反思     ─── 5.5 Reflexion（单轮版）
└─────────┘                                    + 5.7 Eval（基础评分）

┌─────────┐
│  M3     │  ──┬── P5 Eval 评测体系        ─── 5.7 Eval（LLM-as-Judge + Benchmark）
│ 工程    │    │                               + 5.10 工程化（成长仪表盘）
│ 深度    │    ├── P6 高级多 Agent         ─── 5.2 Agent 团队（8/8 完整）
│         │    │                               + 5.3 协作（scratchpad / 动态路由 / HITL / A2A）
│         │    └── P7 Meta-cognition       ─── 5.4 记忆系统（L5 + 知识图谱 6 层完整）
└─────────┘                                    + 5.5 Reflexion（Meta-reflection）
                                               + 5.10 工程化（LangSmith / Langfuse）

┌─────────┐
│  M4     │  ──┬── P8 生态 & 多模态        ─── 5.1 用户层（Mobile / Voice）
│ 商业化  │    │                               + 5.8 MCP Server
│ SaaS    │    │                               + 5.9 Voice 模式
│         │    └── P9 商业化 & 飞轮        ─── 5.1 用户层（注册 / 登录 / 订阅）
└─────────┘                                    + 5.6 RAG 题库（用户贡献 / Benchmark 公开）
                                               + 5.10 工程化（Sentry / Prometheus / PostHog）
                                               + 5.11 商业化（Free / Pro / Enterprise）
```

### 6.5.2 反向索引：每个功能模块在哪个里程碑落地

| 功能模块（§5） | 雏形 | 完善 | 完整 |
|---|---|---|---|
| 5.1 用户层 | M1（聊天 UI 雏形） | M2（面试房间 + 复盘报告） | M4（注册 / Mobile / Voice） |
| 5.2 Agent 团队 | M1（1/8 面试官） | M2（3/8：HR + 技术 + Coach） | M3（8/8 全员） |
| 5.3 多 Agent 协作 | — | M2（顺序流转） | M3（scratchpad + 动态路由 + A2A） |
| 5.4 分级长期记忆 | — | M2（L0-L4 简化） | M3（6 层完整 + 衰减 / 冲突 / 归档） |
| 5.5 Reflexion | — | M2（单轮） | M3（Meta-reflection） |
| 5.6 RAG 题库 | M1（3-5 源） | — | M4（20+ 源 + 用户贡献 + 公开 Benchmark） |
| 5.7 Eval 评测体系 | — | M2（基础评分） | M3（LLM-as-Judge + Benchmark） |
| 5.8 MCP Server | — | — | M4 |
| 5.9 Voice 模式 | — | — | M4 |
| 5.10 工程化 / 可观测 | M1（基础日志） | M2（集成测试 + 异步写入） | M3（LangSmith）+ M4（Sentry / PostHog） |
| 5.11 商业化 | — | — | M4 |

### 6.5.3 阅读路径建议

| 你想看什么 | 去哪里 |
|---|---|
| 产品**终态形态** | §5（11 功能模块）+ §6（4 里程碑） |
| **执行节奏** | §7.1（9 Phase 拆分表）+ §7.2（依赖图） |
| **立即动手**（7 天 ship） | `plans/7-day-ship-plan.md`（M2 兑现切片） |
| 某 Phase **详细技术设计** | 对应 `plans/m*-plan.md` |

---

## 7. 9 Phase 完整拆分与依赖关系

### 7.1 9 Phase 完整拆分表

拆分原则：每个 Phase 必须是「可独立交付 + 内聚成一个完整能力 + 价值有明显跃迁 + 可单独写进简历」的版本。

| Phase | 名称 | 核心交付 | 用户价值跃迁 | 简历叙事节点 | 工期粗估 |
|---|---|---|---|---|---|
| **P0** | **工程地基** | FastAPI + Celery + Redis + pgvector + Next.js 全栈脚手架 / Alembic 迁移 / dev.sh 一键启动 / **Clerk 多用户鉴权（Email + GitHub OAuth + JWT 校验）** / 配置 / 日志 / 错误处理基础设施 | （内部地基，无直接用户价值） | "生产级 Python AI 全栈脚手架，含异步任务、向量库、多用户鉴权" | 16-20h |
| **P1** | **MVP 单 Agent 闭环** | 1 个面试官 Agent + RAG 题库（3-5 源）+ 单轮问答 + SSE 流式 + 最简前端聊天页 | "我能跟 AI 面 Agent 工程师题" | "基于 RAG + LLM 的 AI Agent 工程师面试问答原型" | 20-24h |
| **P2** | **多 Agent 顺序编排** | HR + 技术 + Coach 3 Agent + LangGraph StateGraph + Agent 间状态传递 + 短期记忆 L0 + 面试房间前端完整版 | "我能体验多角色多轮面试" | "LangGraph 多 Agent 编排的全流程面试系统" | 18-24h |
| **P3** | **分级长期记忆系统** | L1 工作记忆 + L2 长期画像 + L3 STAR 故事库 + L4 弱点标签 + 异步读写策略 + 复盘报告页（首版） | "AI 越用越懂我，跨会话记得我项目经历和弱点" | "MemGPT 范式分级长期记忆，跨会话用户建模" | 24-32h |
| **P4** | **Reflexion 自反思** | Reflexion Agent（评分 + 反思 + 改进建议 + 回写记忆）+ 基础反向出题（弱点驱动） | "Agent 给我打分、提建议、针对性出弱点题" | "Reflexion 自反思 + 闭环出题（基于 NeurIPS 2023 论文）" | 10-14h |
| **P5** | **Eval 评测体系** | LLM-as-Judge 多维度评分（clarity / depth / specificity / STAR_completeness）+ 量化进步曲线 + Benchmark 测试集 + 成长仪表盘 | "我能看到自己每周进步多少" | "工程化 LLM-as-Judge Eval + 进步曲线量化" | 30-40h |
| **P6** | **高级多 Agent 协作** | 共享 scratchpad + 动态路由（按表现切 Agent）+ BOSS 终面 Agent + 出题升级 Agent + 记忆管家 Agent + HITL 中途打断 + A2A 通信协议 | "Agent 间真协作，能根据我的状态自动调整" | "高级多 Agent 协作（共享状态 + 动态路由 + A2A 协议）" | 40-50h |
| **P7** | **Meta-cognition + 高级记忆** | L5 反思日志 + Meta-reflection（多场轨迹元反思）+ L4 升级为 Neo4j 弱点知识图谱 + 可视化 + 记忆遗忘衰减 + 冲突解决 + 压缩归档 | "AI 知道我最近的进步轨迹和反复错的盲点" | "Meta-cognition + 知识图谱记忆系统" | 40-50h |
| **P8** | **生态 & 多模态** | MCP Server 化（暴露工具给 Claude Code / Cursor）+ Voice 模式（Realtime API + Whisper/TTS fallback）+ 中英双语 + 移动端响应式 | "我能在 Claude Code 里直接调起面试 / 语音陪练" | "MCP 协议接入 + Realtime Voice + 跨平台" | 60-80h |
| **P9** | **商业化 & 数据飞轮** | Stripe 计费（多用户鉴权已前移到 P0）+ Sentry / Prometheus 监控告警 + PostHog 行为分析 + 用户贡献题库 + 公开 Benchmark 数据集 + 企业版（HR 反向用做候选人筛选） | "对外可售卖 SaaS 产品" | "独立完成的 AI SaaS 产品（X 用户 / Y 题库 / 跨平台 / 企业版）" | 80-120h |

**全产品工期合计**：约 **340-450h**（不考虑学习曲线和并行加速）

### 7.2 Phase 依赖关系图

```
                          P0 工程地基
                               │
                               ▼
                      P1 单 Agent MVP
                               │
                               ▼
                      P2 多 Agent 顺序流转
                               │
                               ▼
                      P3 分级长期记忆系统  ─────────────────┐
                               │                            │
                               ▼                            │
                      P4 Reflexion 自反思                   │
                               │                            │
                               ▼                            │
                      P5 Eval 评测体系                      │
                               │                            │
                               ▼                            │
                      P6 高级多 Agent 协作                  │
                               │                            │
                               ▼                            │
                      P7 Meta-cognition + 高级记忆          │
                               │                            ▼
                               ▼              P9 商业化 & 数据飞轮
                      P8 生态 & 多模态        （可在 P3 之后任意节点并行接入）
                               │                            │
                               └──────────────┬─────────────┘
                                              ▼
                                       完整 SaaS 产品

简历里程碑映射：
  P0 + P1            ──→ M1（原型）
  P2 + P3 + P4       ──→ M2（核心叙事兑现 ★ 7 天 ship 目标）
  P5 + P6 + P7       ──→ M3（工程化深度）
  P8 + P9            ──→ M4（商业化 SaaS）
```

### 7.3 关键依赖说明

| 依赖关系 | 必要原因 |
|---|---|
| **P0 → 任何 Phase** | 任何业务功能都依赖基础设施（DB / Redis / FastAPI / Next.js） |
| **P1 → P2** | 必须先有 1 个能跑的 Agent，再扩展为多 Agent 协作 |
| **P2 → P3** | 必须先有 Agent 框架，才有「在哪个节点读 / 写记忆」的挂载点 |
| **P3 → P4** | 必须先有可写入的记忆层，Reflexion 才有地方回写「评分 / 弱点 / 改进」 |
| **P4 → P5** | 必须先有结构化反思输出，Eval 体系才有数据可量化、做多 Judge 共识 |
| **P5 → P6** | 动态路由依赖「用户表现量化分」，Eval 是动态路由的判定输入 |
| **P6 → P7** | Meta-reflection 需要「多 Agent 协作产生的丰富轨迹」才有元认知素材 |
| **P7 → P8** | MCP Server 暴露的工具需要 M3 全部能力（如 `query_growth` 依赖 P7 Meta-reflection） |
| **P9 可并行** | 多用户系统 / Stripe / 监控可在 P3 之后任意节点插入，与 P4-P8 并行 |

### 7.4 Phase 跳跃风险（如果不按顺序）

| 跳过情形 | 后果 |
|---|---|
| 跳过 P0 直接做 P1 | 脚手架不规范导致后续每个 Phase 都在补地基，慢 30%+ |
| 跳过 P3 直接做 P4 | Reflexion 无处回写，等于纯展示，无法「积累成长」 |
| 跳过 P5 直接做 P6 | 动态路由没有评分依据，只能瞎切 Agent |
| 跳过 P7 直接做 P8 | MCP 工具只能暴露浅层能力，无法兑现「AI 知道我的盲区」 |

---

## 8. 7 天求职版兑现切片

**抽取**：P0 全部 + P1 全部 + P2 全部 + P3 简化版（L0/L2/L3/L4 简化）+ P4 单轮简化版
**简历层面**：兑现到 **M2 节点**，核心叙事 100%
**详见**：`plans/7-day-ship-plan.md`

## 9. 技术栈总览

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + uvicorn（ASGI）+ Celery + Redis（含 Pub/Sub） |
| Agent 编排 | **LangGraph**（StateGraph + Memory + HITL） |
| LLM | `gpt-4o`（主推理）/ `gpt-4o-mini`（轻量任务）/ `claude-opus-4-7`（可选） |
| 数据库 | PostgreSQL 16 + pgvector（向量）+ Neo4j（P7 知识图谱） |
| 搜索 | Tavily / 自建向量检索 + 重排 |
| 爬取 | Firecrawl |
| 前端 | Next.js 16（App Router）+ TypeScript + Tailwind + shadcn/ui |
| 包管理 | **uv**（后端，Python 3.12）/ **pnpm**（前端） |
| 测试 | pytest + pytest-asyncio + httpx + Playwright（E2E） |
| 可观测 | LangSmith / Langfuse（M3）+ Sentry + PostHog（M4） |
| 部署 | Docker Compose（本地）/ Vercel + Railway（生产，M4 开始） |
| MCP | Anthropic MCP SDK（Python，M4） |
| Voice | OpenAI Realtime API（M4） |

## 10. 简历兑现策略

- **M2 完成即可投简历**（7 天版即可触达）
- 简历项目栏 50-80 字模板：
  > **Multi Agent Coach** — 独立设计实现的 AI Agent 工程师面试陪练系统。LangGraph 多 Agent 顺序编排（HR / 技术 / Coach），分级长期记忆系统（MemGPT 范式，L0-L4）跨会话建模用户画像与弱点，Reflexion 自反思链路驱动反向出题。技术栈：FastAPI + Celery + LangGraph + pgvector + Next.js。
- 配套素材：
  - 3 分钟 Demo 视频（必备）
  - 架构图（必备）
  - GitHub 公开仓库（必备）
  - 产品落地页 / Demo URL（M3 后可加）

## 11. 参考资料 & 技术依据

| 模块 | 参考 |
|---|---|
| 分级长期记忆 | **MemGPT** (Packer et al., arXiv 2310.08560) — 主存/外存分级范式 |
| 自反思 | **Reflexion** (Shinn et al., NeurIPS 2023, arXiv 2303.11366) — Actor-Evaluator-Self-Reflection 三角架构 |
| Agent 编排 | LangGraph 官方文档（Multi-Agent + Memory + HITL） |
| 开源记忆库参考 | Mem0 (github.com/mem0ai/mem0) / Letta (前 MemGPT 商业化) |
| Eval | Anthropic Eval Cookbook / LangSmith Eval / OpenAI Evals |
| MCP | Anthropic MCP 官方文档（Quickstart + SDK） |
| 元认知 | Self-Refine (Madaan et al., 2023) / Chain-of-Thought self-evaluation |

## 12. 风险与决策点

| 风险 | 等级 | 应对 |
|---|---|---|
| 题库内容质量决定产品口碑 | 高 | 用户自己是 Agent 候选人，可亲自审核；用 offer-copilot 抓取流水线建库 |
| LangGraph API 持续演进 | 中 | 用 context7 拉取最新文档；M2 完成后锁定版本 |
| 多 Agent 协作复杂度（M3） | 中 | M2 用顺序流转兜底，M3 再升级 |
| 记忆冲突 / 膨胀 | 中 | M2 用「最后写入 + 冲突日志」+ top-K 检索；M3 引入记忆管家 Agent |
| Voice 模式投入大（M4） | 低 | M4 才接入，可选 |
| 撞赛道（Mem0 / Letta） | 低 | 我们垂直到 AI Agent 工程师面试，他们是通用框架，不直接竞争 |

## 13. 后续文档索引

| 文档 | 说明 |
|---|---|
| `plans/m1-foundation.md` | M1 详细计划（P0 + P1） |
| `plans/m2-core.md` | M2 详细计划（P2 + P3 + P4，核心叙事） |
| `plans/m3-engineering.md` | M3 详细计划（P5 + P6 + P7） |
| `plans/m4-saas.md` | M4 详细计划（P8 + P9） |
| `plans/7-day-ship-plan.md` | 7 天求职版 Day-by-Day 执行计划 |

---

**📌 决策待办**：
- [x] **产品名 = `Multi Agent Coach`**（项目代号 / 仓库名 / 目录名 = `multi-agent-coach`）
- [x] **GitHub 仓库 = 公开**（开发起步即建公开仓刷 Star）
- [ ] 域名（M3 后需要，可选 `multiagentcoach.ai` / `multi-agent-coach.dev` 等）
