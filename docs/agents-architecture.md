# `backend/app/agents/` 目录结构解析

该目录是整个项目的 **AI 核心层**，包含 5 个 LangGraph 子 Agent，对应产品的五个阶段。每个 Agent 的内部文件结构完全一致。

---

## 一、整体架构图

```
agents/
├── prepare/        ← 阶段1：备考准备 Agent
├── interviewer/    ← 阶段2：面试主 Agent（编排中枢）
│   ├── chief.py       ← Chief ReAct Loop（核心调度节点）
│   └── chief_prompts.py
├── evaluator/      ← 阶段3：答题评估 Agent（被 chief 调用）
├── designer/       ← 阶段3：出题设计 Agent（被 chief 调用）
└── coach/          ← 阶段4：面试复盘教练 Agent
```

**调用关系**：`interviewer/chief.py` 作为 ReAct Loop，通过 Tool Call 方式调用 `evaluator` 和 `designer`，不是直接调 Python 函数，而是走 LangGraph 子图。

---

## 二、统一文件结构（每个 Agent 都有）

| 文件         | 职责                                                     |
| ------------ | -------------------------------------------------------- |
| `state.py`   | 定义该 Agent 的 `TypedDict` 状态，所有节点通过它共享数据 |
| `nodes.py`   | 每个 LangGraph 节点对应一个异步函数                      |
| `prompts.py` | 该 Agent 的 LLM System Prompt 模板                       |
| `graph.py`   | 组装 LangGraph + 暴露 SSE 流式接口给 API 层              |

---

## 三、各 Agent 详解

### 1. `prepare/` — 备考准备 Agent

**触发时机**：用户提交 JD 或方向后，正式面试前。

**Graph 结构**（带条件路由）：

```
supervisor ──► memory_search ──┐
     ▲         research_agent ──┤──► supervisor ──► jd_analysis ──► question_gen ──► END
     └──────────────────────────┘
```

| 节点             | 干了什么                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------ |
| `supervisor`     | LLM 决策下一步行动（`need_direction` / `memory_search` / `research_agent` / `jd_analysis` / `question_gen`） |
| `memory_search`  | 查数据库，读用户历史薄弱点（`weak_areas`）                                                                   |
| `research_agent` | 调用 job-intel MCP，抓岗位情报（公司画像、简历差距）                                                         |
| `jd_analysis`    | LLM 解析 JD，输出 `JDContext`（岗位/难度/技能点）                                                            |
| `question_gen`   | LLM 按薄弱点+JD 出 N 道定制题                                                                                |

**并行能力**：`memory_search` 与 `research_agent` 可并行执行，通过自定义 `merge_completed_tools` reducer 安全合并。

**输出**：`prepared_questions`（题库）+ `jd_context` + `job_intel`，后续 interviewer 会读取。

---

### 2. `interviewer/` — 面试主 Agent（编排中枢）

**触发时机**：用户每次发送一条消息时。

**Graph 结构**（ReAct Loop）：

```
load_context → chief_think ──► chief_execute ──┐
                    │                           │
                    │          ◄────────────────┘
                    ▼
              chief_respond
                    │
                    ▼
               report → END
```

| 节点            | 干了什么                                                                           |
| --------------- | ---------------------------------------------------------------------------------- |
| `load_context`  | 从 DB 加载 session 上下文、历史消息                                                |
| `chief_think`   | **ReAct 思考**：LLM 分析当前对话，决定调用哪个 Tool（evaluate / design / respond） |
| `chief_execute` | **执行 Tool**：并行调用 `evaluator` 子图或 `designer` 子图                         |
| `chief_respond` | LLM 生成最终面试官回复（问题 or 追问 or 结束语）                                   |
| `report`        | 面试结束时聚合所有 `turn_evaluations`，生成最终报告                                |

**关键设计**：

- 使用 **PostgreSQL checkpointer** 持久化对话状态（`AsyncPostgresSaver`），支持断点续传
- `chief.py` 中有最多 **4 轮 ReAct 迭代**（`MAX_CHIEF_ITERATIONS = 4`）
- 内置终止关键词检测（"结束"、"退出"等），提前收束面试

---

### 3. `evaluator/` — 答题评估 Agent

**触发时机**：被 `chief_execute` 通过 Tool Call 调用。

**Graph 结构**（线性）：

```
analyze_answer → update_profile → respond_to_chief → END
```

| 节点               | 干了什么                                                     |
| ------------------ | ------------------------------------------------------------ |
| `analyze_answer`   | 对当前答题打维度分：技术深度/量化结果/失败复盘/结构/总分     |
| `update_profile`   | 累积更新候选人画像（`CandidateProfile`）：能力等级/信号/盲区 |
| `respond_to_chief` | 将评估结果打包成 `report` 返回给 chief                       |

**输出字段（`TurnEvaluation`）**：`summary_score`、`candidate_level`、`latent_signals`、`missing_dimensions`、`followup_would_help`

---

### 4. `designer/` — 出题设计 Agent

**触发时机**：被 `chief_execute` 通过 Tool Call 调用。

**两种图模式**：

| 模式      | Graph 结构                             | 用途                    |
| --------- | -------------------------------------- | ----------------------- |
| 标准模式  | `design → validate → respond_to_chief` | 出一道题 + 校验 + 打包  |
| Dual 模式 | `design_dual → END`                    | 同时生成当前题 + 后备题 |

**输入**：`focus_area`（追问方向）、已问题列表（去重）、候选人画像、JD 上下文。

---

### 5. `coach/` — 面试复盘教练 Agent

**触发时机**：面试结束后，用户查看复盘报告时。

**Graph 结构**（线性）：

```
load_memory → review → plan → persist → END
```

| 节点          | 干了什么                                         |
| ------------- | ------------------------------------------------ |
| `load_memory` | 读候选人长期记忆（历史表现、简历摘要、岗位情报） |
| `review`      | LLM 生成本场面试的文字复盘（`review_text`）      |
| `plan`        | LLM 生成结构化备考计划（`plan_json`）            |
| `persist`     | 将 review + plan 写入数据库持久化                |

---

## 四、跨 Agent 数据流

```
PrepareState ──► InterviewState (透传 jd_context / job_intel / prepared_questions)
                      │
                      ├──► EvaluatorState (每轮答题)
                      │         │
                      │         └──► TurnEvaluation 累积到 InterviewState
                      │
                      └──► DesignerState (出每道题)

InterviewState.report ──► CoachState (面试结束后)
```

所有 Agent 都通过 `graph.py` 中的 `stream_*_events` 函数向 API 层暴露 **SSE 事件流**（`node_start` / `node_token` / `node_done` / `done`），前端 Trace 面板实时展示的就是这些事件。
