# 面试官 Agent 设计文档（第二步）

**日期**：2026-05-25  
**范围**：单 Agent · LangGraph · Session 持久化  
**目标**：用 LangGraph 实现一个能主持完整模拟面试的单 Agent，并将每次面试 run 与消息数据持久化到 PostgreSQL；产品入口始终围绕 Clerk `user_id`，不让前端或用户感知内部 run/session id。

---

## 一、背景与范围

### 当前状态

`backend/app/services/interview_chat.py` 已实现基础流式对话：每次请求前端带全量历史，后端调 OpenAI 返回 SSE 流。这是无状态的透传，没有状态机、没有 Session 概念、没有追问逻辑。

### 第二步做什么

| 功能 | 说明 |
|------|------|
| LangGraph 图结构 | 6 个节点、条件边、状态机 |
| 面试主循环 | 出题 → 评判 → 追问/下一题/结束 |
| 新老用户区分 | 新用户收集基本信息；老用户确认今日方向 |
| 面试 run 持久化 | PostgreSQL 两张新表，记录一次完整模拟面试及其消息流水 |
| API 重构 | 从无状态改为 user_id 驱动，由后端自动查找/创建当前活跃面试 run |

### 第二步不做什么

- 老用户历史分析与个性化开场（第五步 Coach Agent）
- 评分写入 DB（第四步评估 Agent）
- 多 Agent 协同（第三步起）
- JD/简历上传解析（第三步）

---

## 二、LangGraph 图结构

### 架构选型

采用**阶段图 + ReAct 追问循环**：有清晰的 opening → interview\_loop → closing 阶段，追问轮数由 LLM 判断，计数器防死循环。

### 节点定义

```
START
  ↓
load_context      查 DB，判断 is_first_time
  ↓
opening           新用户：收集岗位/公司/背景；老用户：确认今日方向
  ↓ [⏸ 等待用户确认]
ask_question      生成下一道题（带全量历史），UI 显示"第 N/5 题"
  ↓ [⏸ 等待用户回答]
decide_next       LLM 按四维标准评判，输出结构化 JSON
  ↓ (条件边)
  ├─ followup_count < 2  → followup → [⏸ 等待] → decide_next
  ├─ question_count < 5  → followup_count 重置 → ask_question
  └─ question_count == 5 → closing → END
```

### State 数据结构

```python
class InterviewState(TypedDict):
    # 身份
    session_id: str          # 后端内部面试 run id，不作为产品主入口
    user_id: str
    is_first_time: bool
    # 面试上下文（opening 阶段填入）
    target_role: str        # 目标岗位，e.g. "AI Agent 工程师"
    target_company: str     # 目标公司，e.g. "字节跳动"
    user_background: str    # 项目背景（新用户填写）
    # 对话历史（全量传 LLM，各题共享上下文）
    messages: list[BaseMessage]
    # 流程控制
    stage: Literal["opening", "interview", "closing"]
    question_count: int       # 当前第几题（从 1 开始）
    total_questions: int      # 固定 5（第二步写死，后续可配置）
    followup_count: int       # 当题已追问次数，新题重置为 0
    max_followups: int        # 每题最多追问次数，默认 2
```

---

## 三、decide\_next 节点详细设计

这是 Agent 质量的核心节点，LLM 以"面试评估助手"身份，按四个维度评判候选人回答。

### 四个评判维度

| 维度 | 说明 | 差例 | 好例 |
|------|------|------|------|
| 技术深度 | 是否讲清楚技术原理，而非堆砌名词 | "我用了 LangGraph" | "用 StateGraph 建了三个节点，边的条件是..." |
| 量化结果 | 是否有具体数字 | "性能提升很多" | "延迟从 2s 降到 400ms，p99 提升 60%" |
| 失败与权衡 | 是否主动提到踩坑和取舍 | 只讲成功路径 | "最初用 X，发现 Y 问题，改成 Z" |
| 结构完整性 | STAR 结构是否完整 | 直接讲做了什么 | "背景是... 我负责... 具体做了... 结果..." |

### 结构化输出 Schema

```python
class DecideNextOutput(BaseModel):
    action: Literal["followup", "next_question", "closing"]
    reason: str               # 简短说明判断依据，用于日志
    followup_question: str    # action == "followup" 时有值，否则为空
```

### 触发逻辑

- `followup`：回答有明显短板，且 `followup_count < max_followups`
- `next_question`：回答基本达标，或已追问次数用完
- `closing`：`question_count == total_questions`（优先级最高，不论回答质量）

---

## 四、新老用户区分

### 判断方式

`load_context` 节点查询 `interview_sessions` 表，若该 `user_id` 无历史记录则 `is_first_time = True`。

### 新用户 opening 流程

Agent 依次收集三项信息（可在同一段对话中完成，不必强制三轮问答）：

1. **目标岗位**：你在准备什么方向的面试？
2. **目标公司**：投的是哪类公司（大厂/外企/初创）？
3. **项目背景**：用一两句话介绍你最想练的那个项目。

### 老用户 opening 流程（第二步简化版）

加载最近一场 **`status = 'completed'`** 的 Session 的 `target_role` / `target_company`，询问今日是否继续同方向；若用户想换方向，重新收集岗位/公司信息。如果所有历史 Session 均为 `abandoned`，按新用户流程处理。历史模式分析（"你过去 7 场有个规律..."）留到第五步 Coach Agent。

---

## 五、面试 run 持久化

### 新增数据表

**`interview_sessions`**

> 命名沿用 session，但产品语义是一次内部面试 run。前端不需要创建或管理它；后端根据 Clerk `user_id` 自动查找当前 `in_progress` run，必要时创建新 run。

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id         VARCHAR(64) NOT NULL REFERENCES users(id)
status          VARCHAR(20) NOT NULL DEFAULT 'in_progress'
                -- in_progress | completed | abandoned
stage           VARCHAR(20) NOT NULL DEFAULT 'opening'
                -- opening | interview | closing
target_role     VARCHAR(255)
target_company  VARCHAR(255)
user_background TEXT
total_questions INT NOT NULL DEFAULT 5
question_count  INT NOT NULL DEFAULT 0
followup_count  INT NOT NULL DEFAULT 0
started_at      TIMESTAMPTZ NOT NULL DEFAULT now()
completed_at    TIMESTAMPTZ
```

**`interview_messages`**

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
session_id      UUID NOT NULL REFERENCES interview_sessions(id)
role            VARCHAR(20) NOT NULL   -- user | assistant | system
content         TEXT NOT NULL
question_number INT                    -- 属于第几题（1-5），opening 阶段消息为 NULL，追问与主题共享编号
is_followup     BOOLEAN NOT NULL DEFAULT false
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```

### 持久化时机

- 面试 run 创建：用户第一次进入 `/interview/turn` 且无 `in_progress` run 时，由后端自动写入 `interview_sessions`
- 消息写入：每次 `turn` 完成后，将本轮 user + assistant 消息写入 `interview_messages`
- Session 完成：`closing` 节点执行时更新 `status = 'completed'` 和 `completed_at`

### LangGraph Checkpointer

使用 `langgraph-checkpoint-postgres`（`AsyncPostgresSaver`）持久化图的中间状态，`thread_id` 与内部 `session_id` 保持一致。这样服务重启后图可从断点恢复，不丢失 State；但 API 层仍以登录态中的 `user_id` 为主入口。

---

## 六、API 设计

### 变更对比

| | 旧（无状态） | 新（有状态） |
|---|---|---|
| 请求模型 | 前端带全量 messages | 只带本轮 message，后端从登录态拿 user_id |
| 状态管理 | 无 | 后端 PostgreSQL |
| 接口数量 | 1 个 | 1 个主入口 |

### 新接口

```
POST /api/v1/interview/turn
    Body: { message: string }
    Response: SSE 流
        event: delta  data: { text: "..." }
        event: state  data: { stage, question_count, total_questions }
        event: done   data: {}
        event: error  data: { message: "..." }
```

后端处理流程：

1. 从 Clerk 鉴权结果取得 `user_id`
2. 查询该用户是否有 `status = 'in_progress'` 的内部面试 run
3. 若没有，则根据历史完成记录判断新老用户，并自动创建新的 `interview_sessions`
4. 将本轮用户消息写入 `interview_messages`
5. 调用 LangGraph 推进状态机并流式返回 assistant 回复

新增 `event: state` 事件，让前端可以渲染"第 N/5 题"进度条，无需前端自己维护计数。

---

## 七、对现有代码的影响

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/services/interview_chat.py` | 废弃 | 逻辑迁移到 LangGraph 图 |
| `app/api/v1/interview.py` | 重写 | 新增 `/turn` 主入口，旧 `/chat` 可保留一段时间做兼容 |
| `app/schemas/interview.py` | 扩展 | 新增 Turn 相关 schema |
| `app/models/core.py` | 扩展 | 新增 InterviewSession / InterviewMessage 模型 |
| `alembic/` | 新增迁移 | 添加两张新表 |

新增目录：

```
backend/app/
├── agents/
│   └── interviewer/
│       ├── graph.py        # LangGraph 图定义
│       ├── nodes.py        # 各节点函数
│       ├── state.py        # InterviewState TypedDict
│       └── prompts.py      # 各节点 system prompt
```

---

## 八、测试策略

| 测试类型 | 覆盖点 |
|----------|--------|
| 单元测试 | `decide_next` 的三种 action 输出；`load_context` 新老用户判断；追问上限触发自动跳题 |
| 集成测试 | 完整五题流程走通；追问不超过 2 轮；Session 正确写入 DB；空回答错误路径 |
| 边界测试 | 用户中途断开（Session 状态 abandoned）；空回答处理 |

### LLM Eval（延后至第三步）

当前阶段的单元/集成测试均 mock LLM，不验证 LLM 实际输出质量。真实 LLM 输出的约束验证（例如：弱回答 → `decide_next` 必须返回 `followup`；强回答 → 必须返回 `next_question`）计划在 JD 分析（第三步）落地、prompt 稳定后统一补充。

延后原因：JD 接入后 prompt 会调整，现阶段写 eval case 大概率需要重写；当前用 LangSmith 人工观察足以支撑迭代。

---

## 九、可观测性：LangSmith

LangGraph 图的执行过程不透明，需要 LangSmith 做追踪，在调试和迭代 prompt 时尤其关键。

### 接入方式

只需在环境变量中加入以下配置，LangGraph 自动上报所有节点的执行轨迹：

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls_...          # 从 smith.langchain.com 获取
LANGCHAIN_PROJECT=multi-agent-coach
```

在 `backend/.env` 中添加，通过 `pydantic-settings` 读取，**不硬编码**。

### 可观测内容

- 每个节点的输入/输出 State
- `decide_next` 每次的 action / reason / followup_question
- 每次 LLM 调用的 prompt、token 用量、延迟
- 整张图的执行路径（走了哪条边）

---

## 十、不在本设计范围内

- 评分写入 DB（第四步）
- 老用户历史模式分析（第五步）
- 向量检索（第五步）
- 多 Agent 协同（第三步起）
- JD/简历解析（第三步）
