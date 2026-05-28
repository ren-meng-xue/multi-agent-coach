# Phase 5 设计文档：教练 Agent + 共享记忆层 + 打通完整五阶段流程

**日期**：2026-05-28
**范围**：新增 coach LangGraph 子图 + `candidate_memory` 持久化表 + 五阶段编排串联（prepare → interview → evaluate → coach → report）+ 前端 `/coach` 复盘视图
**目标**：把面试系统从"单次模拟"升级为"长期教练关系"——候选人每场面试结束后，coach 基于跨 session 画像主动给出针对性复盘 + 下一步计划。

**Spec 版本**：v1（用户已确认所有关键决策点，见 §十二）

---

## 一、背景与问题

### 1.1 当前进度

- Phase 1-3：流式对话、单面试官 Agent、JD 出题 Orchestrator 全部已上线。
- Phase 4 + 4+：评估 Agent + 跨轮候选人画像 + 信号驱动追问已落地（commit `4acc5ae` … `0058fc0`）。
- Phase 5 / 6 未启动。

### 1.2 当前 coach 的缺陷

| 现象 | 代码根因 |
|------|---------|
| coach 只能生成"开场词" | `coach_opening.py` 是 service 级一次性 LLM 调用，不是 Agent |
| coach 不会"复盘上一场" | 没有"面试结束 → 触发 coach 节点 → 产出复盘报告"的编排 |
| 跨 session 画像清零 | `candidate_profile` 只活在 LangGraph state（per thread），新开 session 重置（Phase 4+ QA 报告 R3） |
| 教练建议不基于具体行为 | 现有 `improvements` 来自 evaluator 报告，不来自跨场对比 |
| 五阶段没有状态机串联 | 前端靠 URL 跳转，后端没有 stage 状态机记录"用户当前在哪一阶段" |

### 1.3 本期目标（一句话）

让 coach 不只是"开场欢迎"，而是 **基于跨 session 持久化的候选人记忆**，在面试结束时主动产出 **复盘 + 个性化训练计划**，并把 prepare → interview → evaluate → coach → report 五阶段串成有状态的闭环。

---

## 二、五阶段流程定义

「五阶段」在本 Spec 中明确指 **用户产品视角** 的流程，而非开发路线图：

```
1. prepare    → 用户在 /coach 选岗位/上传 JD，系统准备题目（现有 prepare agent）
2. interview  → 用户在 /interview 答题（现有 interviewer agent）
3. evaluate   → 每轮 evaluator 打分（现有 evaluator node，已在 interviewer 子图内）
4. coach      → 面试结束触发 coach agent 复盘 + 生成下一步计划（本期新建）
5. report     → 用户在 /reports 查看历史报告 + 长期趋势（现有页面，本期补 long-term metrics）
```

**关键约束**：evaluate 不独立成阶段入口（它是 interview 内的子节点），但在五阶段中作为"价值产出点"被显式列出。

---

## 三、设计原则

1. **不重构既有 graph**：interviewer / prepare 子图原封不动，coach 是独立子图。
2. **共享记忆层先做 SQL，不引入 Vector DB**：候选人长期画像是结构化数据（level、累积 signals、weakness tags），关系表足够；语义检索属于 Phase 6+ 决策。
3. **coach 触发是显式动作，不是后台**：用户在 `/coach` 主动点击「让教练复盘」才执行，不在面试结束时偷偷跑。
4. **数据流单向**：interview 写记忆层 → coach 读记忆层 + 写计划；coach 不回写 interview state。
5. **失败回退**：coach Agent LLM 失败时，回退到现有 `coach_opening.py` 的开场词逻辑，不让 `/coach` 页面崩溃。
6. **不做的事**：跨用户对比、推荐系统、对话式 coach（仅一次性产出）—— 留给后续阶段。

---

## 四、共享记忆层 schema

### 4.1 新增表：`candidate_memory`

跨 session 的候选人画像汇总，user_id 维度聚合。

```sql
CREATE TABLE candidate_memory (
    user_id          VARCHAR(64) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    latest_level     VARCHAR(20),                    -- beginner / junior / mid / senior
    cumulative_signals JSONB DEFAULT '[]'::jsonb,    -- list[str] 跨 session 去重保序
    weakness_tags    JSONB DEFAULT '[]'::jsonb,      -- list[{tag: str, count: int, last_seen_at: timestamp}]
    last_session_id  UUID REFERENCES interview_sessions(id) ON DELETE SET NULL,
    total_sessions   INT NOT NULL DEFAULT 0,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**决策（已确认）**：`weakness_tags` 用 JSONB，不拆独立表 `weakness_events`。若后续 coach prompt 需要引证具体 session 再迁移到关系表。

### 4.2 新增表：`coach_plans`

每次 coach 复盘产出的训练计划。

```sql
CREATE TABLE coach_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES interview_sessions(id) ON DELETE SET NULL,
    plan_json       JSONB NOT NULL,                  -- 结构化计划（见 §5.1）
    consumed        BOOLEAN NOT NULL DEFAULT false,  -- 是否已被用户进入下一场使用
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_coach_plans_user_unconsumed ON coach_plans(user_id) WHERE consumed = false;
```

### 4.3 与 LangGraph state 的同步

- **interviewer 子图结束时**（report node 后）：写入 `candidate_memory`（upsert）+ 把 session-level `candidate_profile` 合并进 `cumulative_signals`。
- **coach 子图开始时**：从 `candidate_memory` 读取 → 注入 coach agent state。
- **不在 LangGraph state 里复制完整记忆**，只复制本次决策需要的切片。

### 4.4 Alembic 迁移

新增一个 Alembic 版本：

```
backend/alembic/versions/<rev>_add_candidate_memory_and_coach_plans.py
```

按 CLAUDE.md「数据库迁移必须走 Alembic」「禁止直接手改」执行。

---

## 五、Coach Agent 设计

### 5.1 子图节点

新建 `backend/app/agents/coach/`：

```
coach/
├── __init__.py
├── graph.py         # 子图 build / 持久化
├── nodes.py         # 各节点函数
├── prompts.py       # SystemPrompt 集合
└── state.py         # CoachState TypedDict
```

子图节点（线性）：

```
load_memory  → 从 candidate_memory + 最近 N 个 session 读取画像
review_node  → LLM 产出复盘文本（流式）
plan_node    → LLM 结构化输出训练计划
persist_node → 写 coach_plans 表
```

**决策（已确认）**：`review_node` 和 `plan_node` 分两次 LLM 调用——复盘是叙事文本（流式给前端体验好），计划是结构化 JSON（用 structured_output）。

### 5.2 输出 schema（plan_json）

```python
class CoachPlan(BaseModel):
    summary: str                          # 一句话总结本次面试
    strengths: list[str]                  # 2-3 条具体亮点
    weaknesses: list[str]                 # 2-3 条具体短板
    next_focus_areas: list[str]           # 下次面试要重点练的方向
    recommended_role: str | None          # 推荐下一场练什么岗位
    recommended_question_types: list[str] # 推荐题型
```

### 5.3 prompts

- `COACH_REVIEW_SYSTEM_PROMPT`：基于 candidate_memory + 最近一场 session 产出叙事复盘
- `COACH_PLAN_SYSTEM_PROMPT`：基于复盘 + 历史 weakness_tags 产出 structured plan
- 复用 `coach_opening.py` 的"禁用万金油"约束（不准说"提升空间 / 加油 / 继续努力"）

### 5.4 API endpoint

```
POST /api/v1/coach/review?session_id=<uuid>
  → SSE 流：review_token / plan_done / final
  → 200: { plan_id: uuid }

GET /api/v1/coach/plans/latest
  → 200: CoachPlan | null
```

### 5.5 与现有 `coach_opening.py` 的关系

- **不删除**。`coach_opening` 继续负责 `/coach` 页面进入时的开场词（不变）。
- 新 coach Agent 由用户在 `/coach` 页面 **显式点击**「让教练复盘」按钮触发，只在有未消费的最近 session 时可点。
- coach_opening 内部可以引用最新 `CoachPlan.next_focus_areas` 作为开场词素材（小改）。

---

## 六、五阶段编排

### 6.1 状态机（派生函数）

**决策（已确认）**：不新增持久化字段，stage 由 **派生函数** 实时计算，避免双写不一致。

```python
# backend/app/services/user_stage.py
from typing import Literal

UserStage = Literal["prepare", "interview", "coach"]

async def derive_user_stage(db: AsyncSession, user_id: str) -> UserStage:
    # 1) 有 in_progress session → interview
    if await has_in_progress_session(db, user_id):
        return "interview"

    # 2) 最近一场 completed session 且没有对应 coach_plans → coach
    last_completed = await get_last_completed_session(db, user_id)
    if last_completed and not await has_coach_plan_for(db, last_completed.id):
        return "coach"

    # 3) 否则 prepare（无 session 或最近 session 的 plan 已生成）
    return "prepare"
```

- `prepare`：默认态，引导用户开始下一场
- `interview`：有 status='in_progress' 的 session
- `coach`：最近 session 已 completed 但 coach_plans 未生成
- **`report` 不在派生集**：报告是用户主动浏览历史，由 URL 直接访问，不是系统引导阶段

前端按派生 stage 渲染不同 CTA，每次进入 `/coach` 时调用 `GET /api/v1/user/stage`。

### 6.2 阶段转换触发点

| 转换 | 触发位置 |
|------|---------|
| prepare → interview | `POST /api/v1/sessions` 创建 session 时 |
| interview → coach | session.status 从 in_progress 转 completed 时 |
| coach → report | coach_plans 写入成功时 |
| report → prepare | 用户点「开始下一场」触发新 session 时 |

### 6.3 SSE / 前端透传

- 现有 `/interview` SSE 不变。
- 新 `/api/v1/coach/review` SSE：
  - `review_token`：复盘叙事流式 token
  - `plan_done`：plan_json 完成
  - `final`：{plan_id}
- 前端 `/coach` 页面新增"教练复盘"区块，对接 SSE。

---

## 七、前端改造

### 7.1 `/coach` 页面升级

现有 `coach-dashboard.tsx` 已经渲染：开场词 + 最近 sessions + 推荐 CTA。

**追加**（不重写）：
- "上一场教练复盘" 区块：渲染 `CoachPlan`，可触发"让教练再复盘一遍"
- 长期 weakness 趋势 chips（来自 `candidate_memory.weakness_tags`）

### 7.2 各阶段 URL 跳转

| 阶段 | 路由 |
|------|------|
| prepare | `/coach` |
| interview | `/interview` |
| evaluate | （interview 内嵌） |
| coach | `/coach`（同 prepare，但展示 plan 区块） |
| report | `/reports` |

不增加新页面，全部复用现有路由。

### 7.3 不动的部分

- `/reports` 页面本期不改（Phase 6 再做长期 metrics）
- `/dashboard` 不动（v1 实验性页面，可能后续删）
- `/settings` 不动

---

## 八、测试策略

### 8.1 后端单测（pytest）

- `tests/unit/test_candidate_memory.py`：upsert 累积 / 去重保序 / 边界
- `tests/unit/test_coach_review_node.py`：review_node 输出非空 / 引用了 cumulative_signals
- `tests/unit/test_coach_plan_node.py`：plan_node structured output / 失败回退
- `tests/unit/test_coach_persist.py`：plan 写表 / coach_plans 索引生效
- `tests/integration/test_coach_endpoint.py`：SSE 流事件顺序 / DB 写入

### 8.2 前端单测（vitest）

- `app/coach/coach-plan-card.test.tsx`：plan 渲染 / 加载态 / 空态
- `app/coach/coach-review-button.test.tsx`：按钮可用/禁用条件

### 8.3 端到端手工 QA 脚本

按 `docs/superpowers/qa-reports/phase4-qa-report.md` 的格式，准备一个跨 session 的 5 阶段流程脚本：
- 第一场面试 → 完成 → coach 复盘 → 第二场面试（验证记忆引用）

---

## 九、风险与回退

| 编号 | 风险 | 缓解 |
|------|------|------|
| R1 | `candidate_memory.cumulative_signals` 长期单调增长，无清理机制 | v0 上限 50 条（FIFO）；超出报警 |
| R2 | LLM 复盘可能"幻觉"引用不存在的 session 细节 | review_node prompt 强制要求引用 session_id；前端展示时校验 |
| R3 | stage 派生函数若 `coach_plans` 写入失败，用户会卡在 `coach` 态 | persist_node 用事务保证 plan_json + coach_plans 行原子写入；失败时 API 返回 503 并提示重试 |
| R4 | coach Agent 失败时整个 `/coach` 页面挂掉 | coach_opening 兜底；coach plan 区块独立加载 |
| R5 | Alembic 迁移线上失败 | 加 `IF NOT EXISTS`；预演 downgrade |

---

## 十、明确不做的事

- 跨用户的"相似候选人"推荐（需要 vector embedding）
- 对话式 coach（一来一回的多轮咨询）
- coach 主动 push 通知（邮件 / 站内信）
- LLM-as-Judge 评估 coach 输出质量（Phase 6 范围）
- 修改 interviewer / prepare 已有 graph 拓扑
- 重写 `coach_opening.py`（仅小幅引用 plan 字段）

---

## 十一、交付检查表

- [ ] Alembic 迁移可上可下
- [ ] `candidate_memory` upsert 测试覆盖
- [ ] coach Agent 子图单测 + 集成测
- [ ] SSE `/api/v1/coach/review` 工作
- [ ] 前端 `/coach` 复盘区块渲染
- [ ] `current_stage` 派生逻辑（或字段）落地
- [ ] 跨 session 手工 QA 通过
- [ ] 风险 R1-R5 至少有缓解或显式接受
- [ ] Phase 5 QA 报告落档

---

## 十二、已确认的关键决策

| 编号 | 问题 | 决策 | 决策日期 |
|------|------|------|---------|
| Q1 | "五阶段"定义是否就用 §2 这套（prepare / interview / evaluate / coach / report）？ | ✅ 采用 | 2026-05-28 |
| Q2 | `weakness_tags` 用 JSONB 还是拆 `weakness_events` 独立表？ | JSONB（不拆） | 2026-05-28 |
| Q3 | `review_node` + `plan_node` 拆两次 LLM 调用还是合并？ | 拆两次 | 2026-05-28 |
| Q4 | `current_stage` 用持久化字段还是派生函数？ | 派生函数 | 2026-05-28 |
| Q5 | coach 是否需要"持续对话"能力？ | ❌ 本期只做一次性产出 | 2026-05-28 |
| Q6 | 是否引入 Vector DB 做长期记忆检索？ | ❌ Phase 6+ 再决策 | 2026-05-28 |

---

## 十三、估算

- 后端：candidate_memory + Alembic + coach subgraph ≈ 1 天
- 前端：coach plan 区块 + SSE 接入 ≈ 0.5 天
- 测试：8.1 + 8.2 ≈ 0.5 天
- 端到端 QA + 报告 ≈ 0.5 天

**总计 2-3 个工作日**（含 review + commit gate）。
