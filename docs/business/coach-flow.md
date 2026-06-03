# 面试后复盘阶段（Coach Flow）

依赖：[overview.md](overview.md) | [multi-agent-interview.md](multi-agent-interview.md)

接口：`POST /coach/review?session_id=<uuid>` → Coach Graph → SSE 流式响应

---

## 1. 功能定位

面试结束后，用户在 `/coach` 页面触发复盘。Coach Agent 读取跨 session 的候选人画像（`candidate_memory`）和本场面试报告，生成叙事复盘文本 + 结构化训练计划，持久化后供下次备考使用。

---

## 2. 整体流程

```
面试结束（interview_sessions.status = "completed"）
        │
        ▼ POST /coach/review?session_id=<uuid>
        │  （鉴权：session 必须属于当前用户）
        │
        ▼
┌──────────────────────────────────────────┐
│              Coach Graph                  │
│                                          │
│  load_memory_node                        │
│    ├─ 读 candidate_memory（user 维度）    │
│    ├─ 读 interview_sessions.report_json  │
│    └─ 读 users.resume_summary            │
│         │                                │
│         ▼                                │
│  review_node                             │
│    └─ LLM 流式生成复盘叙事文本           │
│         │  tag: coach_review_stream      │
│         ▼                                │
│  plan_node                               │
│    └─ LLM 生成 CoachPlanSchema（结构化） │
│         │                                │
│         ▼                                │
│  persist_node                            │
│    └─ 幂等写入 coach_plans（有则更新）   │
└──────────────────────────────────────────┘
        │
        ▼ SSE 推送至前端
```

---

## 3. 各节点详情

### 3.1 load_memory_node

**文件**：`backend/app/agents/coach/nodes.py`

```
load_memory_node(state)
  ├─ SELECT COUNT(*) FROM interview_sessions
  │     WHERE user_id = ? AND status = 'completed' AND score IS NOT NULL
  │     → total_sessions（历史总场次）
  │
  ├─ SELECT * FROM candidate_memory WHERE user_id = ?
  │     → latest_level / cumulative_signals / weakness_tags
  │     （无记录时返回空结构，不报错）
  │
  ├─ SELECT * FROM interview_sessions WHERE id = session_id
  │     → last_session_report（report_json）/ target_role
  │
  └─ SELECT resume_summary FROM users WHERE id = user_id
        → resume_summary（可为 None）
```

### 3.2 review_node

**文件**：`backend/app/agents/coach/nodes.py`

```
review_node(state)
  └─ _generate_review_text(state)
       ├─ 模型：openai_model_chat，streaming=True
       ├─ tag：coach_review_stream（用于 SSE token 捕获）
       ├─ 输入上下文：
       │     【候选人长期记忆】candidate_memory JSON
       │     【最近一场面试表现】target_role + last_session_report JSON
       │     【候选人简历摘要】resume_summary（可选）
       └─ 输出：review_text（str，自然语言叙事）
       retry: 最多 3 次，指数退避，失败兜底返回提示文本
```

### 3.3 plan_node

**文件**：`backend/app/agents/coach/nodes.py`

```
plan_node(state)
  └─ _generate_structured_plan(state)
       ├─ 模型：openai_model_chat，with_structured_output(CoachPlanSchema)
       ├─ 输入上下文：
       │     【复盘总结】review_text
       │     【候选人长期画像】candidate_memory JSON
       │     【本次练习岗位】target_role
       │     【候选人简历摘要】resume_summary（可选）
       └─ 输出：plan_json（CoachPlanSchema.model_dump()）
       retry: 最多 3 次，失败兜底返回最小化降级计划
```
    
**CoachPlanSchema 字段**：

| 字段                         | 类型        | 说明                         |
| ---------------------------- | ----------- | ---------------------------- |
| `summary`                    | str         | 一句话总结本次面试核心结论   |
| `strengths`                  | list[str]   | 2-3 条有引证的亮点           |
| `weaknesses`                 | list[str]   | 2-3 条亟需改进的短板         |
| `next_focus_areas`           | list[str]   | 下次面试要重点练习的方向     |
| `recommended_role`           | str \| None | 推荐下一场练习的岗位         |
| `recommended_question_types` | list[str]   | 推荐题型（技术题 / HR 题等） |

### 3.4 persist_node

**文件**：`backend/app/agents/coach/nodes.py`

```
persist_node(state)
  ├─ SELECT * FROM coach_plans WHERE session_id = ?
  │
  ├─ 已存在 → UPDATE plan_json + consumed = false（允许重新练习）
  └─ 不存在 → INSERT INTO coach_plans
                  user_id / session_id / plan_json / consumed=false
  失败时 rollback，返回 plan_id = None
```

---

## 4. SSE 输出格式

`POST /coach/review` 返回 SSE 流：

```
event: review_token
data: {"token": "..."}          ← review_node 的流式文本 token

event: plan_done
data: {CoachPlanSchema JSON}    ← plan_node 完成后完整计划

event: final
data: {"plan_id": "<uuid>"}     ← persist_node 完成后的计划 ID

event: error
data: {"message": "...", "code": "coach_review_error"}
```

---

## 5. 其他接口

| 接口                         | 说明                                                        |
| ---------------------------- | ----------------------------------------------------------- |
| `GET /coach/opening-message` | 读取用户历史数据，生成 `/coach` 页面个性化开场词            |
| `GET /coach/plans/latest`    | 返回最新一份 `consumed=false` 的计划；无计划时 `data: null` |

---

## 6. 数据模型

### `candidate_memory` 表（user 维度，Evaluator 写入，Coach 读取）

| 字段                 | 类型           | 说明                       |
| -------------------- | -------------- | -------------------------- |
| `user_id`            | VARCHAR(64) PK | 关联 users.id              |
| `latest_level`       | VARCHAR(20)    | 最新候选人水平评级         |
| `cumulative_signals` | JSONB          | 跨 session 累积的行为信号  |
| `weakness_tags`      | JSONB          | 弱点标签列表               |
| `last_session_id`    | UUID           | 最近一场面试 ID            |
| `total_sessions`     | int            | 已完成且有评分的面试总场次 |
| `updated_at`         | TIMESTAMPTZ    | 每次 Evaluator 写入时更新  |

### `coach_plans` 表

| 字段         | 类型        | 说明                                      |
| ------------ | ----------- | ----------------------------------------- |
| `id`         | UUID PK     | 计划唯一 ID                               |
| `user_id`    | VARCHAR(64) | 关联 users.id                             |
| `session_id` | UUID        | 关联 interview_sessions.id                |
| `plan_json`  | JSONB       | CoachPlanSchema 序列化结果                |
| `consumed`   | bool        | false = 尚未按计划开始练习；true = 已消费 |
| `created_at` | TIMESTAMPTZ | 创建时间                                  |

索引：`idx_coach_plans_user_unconsumed`（user_id，WHERE consumed = false）

---

## 7. 关键文件索引

| 文件                                    | 说明                                  |
| --------------------------------------- | ------------------------------------- |
| `backend/app/agents/coach/graph.py`     | Coach Graph 组装 + SSE 流式执行       |
| `backend/app/agents/coach/nodes.py`     | 四个节点函数 + LLM 封装               |
| `backend/app/agents/coach/state.py`     | CoachState TypedDict 定义             |
| `backend/app/agents/coach/prompts.py`   | COACH_REVIEW_SYSTEM_PROMPT / PLAN     |
| `backend/app/api/v1/coach.py`           | `/coach/review`、`/plans/latest` 接口 |
| `backend/app/services/coach_opening.py` | 开场词生成逻辑                        |
| `backend/app/models/core.py`            | CandidateMemory / CoachPlan ORM       |
