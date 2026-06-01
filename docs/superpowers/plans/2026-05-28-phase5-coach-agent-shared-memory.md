# Phase 5 实施 Plan（按 TDD 分步）

**对应 Spec**：`docs/superpowers/specs/2026-05-28-phase5-coach-agent-shared-memory-design.md`
**目标**：教练 Agent + 共享记忆层 + 打通五阶段流程，分 8 个可独立验证的小步落地，每步先写失败测试再实现。

---

## 总体策略

- **TDD**：每步先写/扩展失败测试，再实现，再跑测试。
- **小步可回滚**：每步独立 commit（等待用户确认后才 commit）。
- **不并行改 graph 拓扑**：interviewer / prepare 已有 graph 完全不动，coach 是独立新子图。
- **DB 迁移走 Alembic**：禁止手改表结构（CLAUDE.md 后端规范第 3-4 条）。
- **mock LLM**：不调真实 OpenAI，coach 节点测试用 `unittest.mock.AsyncMock` mock 各 LLM 入口。
- **DB 测试用真实 Postgres**：service / endpoint 层测试不 mock DB（避免 mock/真实 schema 漂移）。
- **验证命令**（每步实现后跑）：
  - 后端：`cd backend && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy app && .venv/bin/python -m pytest tests/`
  - 前端：`cd frontend && pnpm test && pnpm typecheck`
- **完整验证 + 端到端 QA 留到 Step 8**：避免中间步骤 build 慢拖累迭代。

---

## Step 1 · DB schema + Alembic 迁移（地基）

**目标**：建 `candidate_memory` + `coach_plans` 表 + ORM 模型 + Alembic 双向迁移。**不写业务逻辑**。

### 1.1 改动文件
- `backend/app/models/core.py`
  - 新增 `CandidateMemory` Mapped class（PK = user_id，FK → users.id）
  - 新增 `CoachPlan` Mapped class（PK = uuid，FK → users.id + interview_sessions.id）
- `backend/alembic/versions/<rev>_add_candidate_memory_and_coach_plans.py`
  - `upgrade`：创建两表 + 索引 `idx_coach_plans_user_unconsumed`
  - `downgrade`：DROP 两表

### 1.2 失败测试（新增 `backend/tests/unit/test_candidate_memory_model.py`）

```python
def test_candidate_memory_table_exists():
    from app.models.core import CandidateMemory
    assert CandidateMemory.__tablename__ == "candidate_memory"

def test_candidate_memory_fields():
    from app.models.core import CandidateMemory
    cm = CandidateMemory(
        user_id="user_abc",
        latest_level="junior",
        cumulative_signals=["workflow_orchestration"],
        weakness_tags=[{"tag": "quantification", "count": 2}],
        total_sessions=3,
    )
    assert cm.latest_level == "junior"

def test_coach_plan_fields():
    from app.models.core import CoachPlan
    cp = CoachPlan(user_id="user_abc", plan_json={"summary": "x"}, consumed=False)
    assert cp.consumed is False
```

集成测试（新增 `backend/tests/integration/test_alembic_migration.py`）：

```python
@pytest.mark.asyncio
async def test_alembic_upgrade_then_downgrade(engine):
    # 跑 alembic upgrade head → 检查表存在 → downgrade -1 → 表消失
    ...
```

### 1.3 验证
- 新测试先失败（class 不存在 / 表不存在）
- 实现后跑 `pytest tests/unit/test_candidate_memory_model.py tests/integration/test_alembic_migration.py`
- 本地执行 `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` 一次，确认双向可用

### 1.4 风险
- 中。Alembic 迁移上线失败会卡住整个部署。
- 缓解：所有 `CREATE TABLE` 加 `IF NOT EXISTS`；downgrade 用 `DROP TABLE IF EXISTS`。

### 1.5 检查点
- 给用户报"Step 1 done，是否 commit"
- 提议 commit 消息：`feat(db): add candidate_memory and coach_plans tables`

---

## Step 2 · candidate_memory upsert service

**目标**：纯 service 层函数，输入 (user_id, session-level profile)，把 candidate_memory upsert。**不接入任何 graph**。

### 2.1 改动文件
- `backend/app/services/candidate_memory.py`（新建）
  - `async def upsert_candidate_memory(db, user_id, *, latest_level, latent_signals, weakness_tags, session_id) -> CandidateMemory`
  - 内部逻辑：合并 cumulative_signals（去重保序，上限 50 条 FIFO）、合并 weakness_tags（同 tag count+1 + last_seen_at 更新）

### 2.2 失败测试（新增 `backend/tests/unit/test_candidate_memory_service.py`）

```python
@pytest.mark.asyncio
async def test_upsert_creates_row_when_absent(db, user):
    from app.services.candidate_memory import upsert_candidate_memory
    mem = await upsert_candidate_memory(
        db, user.id,
        latest_level="junior",
        latent_signals=["a", "b"],
        weakness_tags=["quantification"],
        session_id=None,
    )
    assert mem.latest_level == "junior"
    assert mem.cumulative_signals == ["a", "b"]

@pytest.mark.asyncio
async def test_upsert_dedup_signals_preserve_order(db, user):
    # 先 upsert ["a", "b"]，再 upsert ["b", "c"]，期望 ["a", "b", "c"]
    ...

@pytest.mark.asyncio
async def test_weakness_tag_count_increments(db, user):
    # 同 tag 出现两次，count == 2，last_seen_at 更新
    ...

@pytest.mark.asyncio
async def test_signals_capped_at_50_fifo(db, user):
    # 累积 60 条，只保留最近 50 条
    ...
```

### 2.3 验证
- pytest 4 个测试全绿
- ruff + mypy 通过

### 2.4 风险
- 低。纯 service，无外部依赖。

### 2.5 检查点
- 提议 commit：`feat(coach): add candidate_memory upsert service`

---

## Step 3 · interviewer report_node 接入 candidate_memory

**目标**：interviewer 子图 `report_node` 结束时调用 Step 2 的 upsert，把本场 session 的 `candidate_profile` 持久化到 `candidate_memory`。**不动 graph 拓扑**。

### 3.1 改动文件
- `backend/app/agents/interviewer/nodes.py`
  - `report_node` 末尾追加：从 `state.candidate_profile` 提取信号 + 从 `turn_evaluations` 聚合 weakness_tags → 调 `upsert_candidate_memory`
  - 失败不阻塞（log warning，按 CLAUDE.md 后端规范第 12 条）

### 3.2 失败测试（新增到 `test_interviewer_evaluator_node.py` 或新建 `test_interviewer_report_node.py`）

```python
@pytest.mark.asyncio
async def test_report_node_writes_candidate_memory(monkeypatch):
    called = {}
    async def fake_upsert(db, user_id, **kwargs):
        called.update(kwargs); called["user_id"] = user_id
        return MagicMock()
    monkeypatch.setattr("app.agents-1.interviewer.nodes.upsert_candidate_memory", fake_upsert)
    state = {
        "user_id": "user_abc",
        "session_id": "...",
        "candidate_profile": {"latest_level": "junior", "latent_signals": ["a"]},
        "turn_evaluations": [{"missing_dimensions": ["quantification"]}],
        ...
    }
    await report_node(state)
    assert called["user_id"] == "user_abc"
    assert called["latest_level"] == "junior"

@pytest.mark.asyncio
async def test_report_node_swallows_upsert_failure(monkeypatch):
    # upsert 抛错时 report_node 仍正常返回，且 log 一条 warning
    ...
```

### 3.3 验证
- pytest 2 个测试全绿
- 现有 interviewer 137 测试全保持通过

### 3.4 风险
- 中。改了 interviewer 的产出动作。
- 缓解：所有逻辑包在 `try/except` 里，失败仅 log warning，不影响 report_json 返回。

### 3.5 检查点
- 提议 commit：`feat(interviewer): persist candidate profile to memory on report`

---

## Step 4 · user stage 派生函数 + API endpoint

**目标**：实现 `derive_user_stage` + `GET /api/v1/user/stage`。前端按此路由决定首屏 CTA。

### 4.1 改动文件
- `backend/app/services/user_stage.py`（新建）
  - `async def derive_user_stage(db, user_id) -> Literal["prepare", "interview", "coach"]`
- `backend/app/api/v1/user.py`（新增或扩展）
  - `GET /user/stage` → `{"stage": "prepare"}`

### 4.2 失败测试（新增 `backend/tests/unit/test_user_stage.py`）

```python
@pytest.mark.asyncio
async def test_stage_prepare_when_no_sessions(db, user):
    assert await derive_user_stage(db, user.id) == "prepare"

@pytest.mark.asyncio
async def test_stage_interview_when_in_progress(db, user, in_progress_session):
    assert await derive_user_stage(db, user.id) == "interview"

@pytest.mark.asyncio
async def test_stage_coach_when_completed_no_plan(db, user, completed_session_no_plan):
    assert await derive_user_stage(db, user.id) == "coach"

@pytest.mark.asyncio
async def test_stage_prepare_when_completed_with_plan(db, user, completed_session_with_plan):
    assert await derive_user_stage(db, user.id) == "prepare"
```

新建 `backend/tests/integration/test_user_stage_endpoint.py`：

```python
@pytest.mark.asyncio
async def test_get_user_stage_endpoint(client, dev_auth_token):
    resp = await client.get("/api/v1/user/stage", headers={"Authorization": dev_auth_token})
    assert resp.status_code == 200
    assert resp.json()["stage"] in ("prepare", "interview", "coach")
```

### 4.3 验证
- pytest 5 个测试全绿
- 手动 curl 一次确认 endpoint 在线

### 4.4 风险
- 低。纯查询，无写入。

### 4.5 检查点
- 提议 commit：`feat(coach): derive user stage from session and plan state`

---

## Step 5 · coach LangGraph 子图（最重的一步）

**目标**：搭建 `backend/app/agents/coach/` 子图（load_memory → review_node → plan_node → persist_node）+ prompts。

### 5.1 改动文件
- `backend/app/agents/coach/state.py`（新建）：`CoachState` TypedDict
- `backend/app/agents/coach/prompts.py`（新建）：`COACH_REVIEW_SYSTEM_PROMPT` / `COACH_PLAN_SYSTEM_PROMPT`
- `backend/app/agents/coach/nodes.py`（新建）：4 个节点函数
- `backend/app/agents/coach/graph.py`（新建）：StateGraph 组装 + `build_coach_graph` / `stream_coach_review_events`
- `backend/app/agents/coach/__init__.py`

### 5.2 失败测试（新增 `backend/tests/unit/test_coach_nodes.py`）

```python
@pytest.mark.asyncio
async def test_load_memory_reads_candidate_memory(monkeypatch, db, user, memory):
    from app.agents.coach.nodes import load_memory_node
    state = {"user_id": user.id, "session_id": memory.last_session_id}
    result = await load_memory_node(state)
    assert result["candidate_memory"]["latest_level"] == memory.latest_level

@pytest.mark.asyncio
async def test_review_node_streams_and_produces_text():
    from app.agents.coach.nodes import review_node
    with patch("app.agents-1.coach.nodes._coach_review_stream", new=AsyncMock(return_value="复盘文本")):
        result = await review_node({"candidate_memory": {...}, "last_session": {...}})
    assert result["review_text"] == "复盘文本"

@pytest.mark.asyncio
async def test_plan_node_structured_output():
    from app.agents.coach.nodes import plan_node, CoachPlanSchema
    fake = MagicMock(spec=CoachPlanSchema, summary="x", strengths=[], weaknesses=[],
                    next_focus_areas=["arch"], recommended_role=None, recommended_question_types=[])
    with patch("app.agents-1.coach.nodes._coach_plan_decide", new=AsyncMock(return_value=fake)):
        result = await plan_node({"review_text": "...", "candidate_memory": {...}})
    assert result["plan_json"]["next_focus_areas"] == ["arch"]

@pytest.mark.asyncio
async def test_plan_node_failure_falls_back():
    """LLM 失败时 plan_json 退化为最小可用结构，不抛错。"""
    ...

@pytest.mark.asyncio
async def test_persist_node_writes_coach_plan(db, user, session):
    from app.agents.coach.nodes import persist_node
    state = {"user_id": user.id, "session_id": session.id,
             "plan_json": {"summary": "x", ...}}
    result = await persist_node(state)
    assert result["plan_id"] is not None
    row = await db.get(CoachPlan, result["plan_id"])
    assert row.plan_json["summary"] == "x"
```

### 5.3 验证
- pytest 5 个 coach 节点测试全绿
- ruff + mypy 通过
- 不跑端到端，留到 Step 8

### 5.4 风险
- 中。新子图，LLM 调用最多。
- 缓解：所有 LLM 调用按 CLAUDE.md 第 8 条加 `tenacity` retry + 30s timeout + 失败 log；plan_node 失败有兜底。

### 5.5 检查点
- 提议 commit：`feat(coach): add coach langgraph subgraph with review and plan nodes`

---

## Step 6 · coach API endpoint + SSE

**目标**：暴露 `POST /api/v1/coach/review` SSE + `GET /api/v1/coach/plans/latest`。

### 6.1 改动文件
- `backend/app/api/v1/coach.py`（新建或扩展）
  - `POST /coach/review?session_id=<uuid>` → SSE 流（`review_token` / `plan_done` / `final`）
  - `GET /coach/plans/latest` → `CoachPlan | null`
- `backend/app/schemas/coach.py`（新建）：`CoachPlanResponse` / `CoachReviewEvent`

### 6.2 失败测试（新增 `backend/tests/integration/test_coach_endpoint.py`）

```python
@pytest.mark.asyncio
async def test_coach_review_sse_event_sequence(client, dev_auth_token, completed_session):
    """SSE 顺序：review_token+ → plan_done → final"""
    events = []
    async with client.stream("POST", f"/api/v1/coach/review?session_id={completed_session.id}",
                              headers={"Authorization": dev_auth_token}) as resp:
        async for line in resp.aiter_lines():
            ...
    names = [e["event"] for e in events]
    assert names[-2] == "plan_done"
    assert names[-1] == "final"
    assert "review_token" in names

@pytest.mark.asyncio
async def test_coach_review_writes_plan_row(client, dev_auth_token, completed_session, db):
    await client.post(f"/api/v1/coach/review?session_id={completed_session.id}", ...)
    plans = (await db.execute(select(CoachPlan).where(CoachPlan.session_id == completed_session.id))).scalars().all()
    assert len(plans) == 1

@pytest.mark.asyncio
async def test_get_latest_plan_returns_null_when_absent(client, dev_auth_token):
    resp = await client.get("/api/v1/coach/plans/latest", headers={"Authorization": dev_auth_token})
    assert resp.status_code == 200
    assert resp.json() is None

@pytest.mark.asyncio
async def test_coach_review_rejects_other_users_session(client, dev_auth_token, other_user_session):
    resp = await client.post(f"/api/v1/coach/review?session_id={other_user_session.id}", ...)
    assert resp.status_code == 403
```

### 6.3 验证
- pytest 4 个集成测试全绿
- 手动 curl SSE 一次确认 token 顺序

### 6.4 风险
- 中。SSE 配置不当可能在生产卡住连接。
- 缓解：复用 interviewer SSE 的 `EventSourceResponse` 模板；30s 心跳。

### 6.5 检查点
- 提议 commit：`feat(coach): add coach review sse endpoint and latest plan getter`

---

## Step 7 · 前端 /coach 复盘区块 + stage CTA

**目标**：前端 `/coach` 页面追加"教练复盘"区块 + 按 stage 渲染不同 CTA。**不重写现有 dashboard**。

### 7.1 改动文件
- `frontend/lib/coach-types.ts`（新建或扩展）：`CoachPlan` / `UserStage` 类型
- `frontend/lib/coach-api.ts`（新建）：`fetchUserStage()` / `fetchLatestPlan()` / `streamCoachReview()`
- `frontend/app/coach/coach-plan-card.tsx`（新建）：渲染单个 plan
- `frontend/app/coach/coach-review-button.tsx`（新建）：触发 SSE 复盘
- `frontend/app/coach/coach-dashboard.tsx`（追加）：嵌入上面两个组件 + stage CTA 切换

### 7.2 失败测试（新增到 `app/coach/`）

```tsx
// coach-plan-card.test.tsx
test("renders plan summary and focus areas", () => {
  render(<CoachPlanCard plan={{summary: "x", next_focus_areas: ["arch"], ...}} />);
  expect(screen.getByText(/arch/)).toBeInTheDocument();
});

test("shows empty state when plan is null", () => {
  render(<CoachPlanCard plan={null} />);
  expect(screen.getByTestId("coach-plan-empty")).toBeInTheDocument();
});

// coach-review-button.test.tsx
test("disabled when stage !== coach", () => {
  render(<CoachReviewButton stage="prepare" sessionId="..." />);
  expect(screen.getByRole("button")).toBeDisabled();
});

test("enabled when stage === coach", () => {
  render(<CoachReviewButton stage="coach" sessionId="..." />);
  expect(screen.getByRole("button")).toBeEnabled();
});
```

### 7.3 验证
- vitest 4 个测试全绿
- typecheck 清

### 7.4 风险
- 低。纯 UI 追加。

### 7.5 检查点
- 提议 commit：`feat(frontend): add coach review plan card and stage-aware cta`

---

## Step 8 · 完整验证 + 端到端 QA + 文档对账

### 8.1 跑全套验证
```bash
cd backend && .venv/bin/python -m ruff check .
cd backend && .venv/bin/python -m mypy app
cd backend && .venv/bin/python -m pytest tests/

cd frontend && pnpm test
cd frontend && pnpm typecheck
cd frontend && pnpm build
```

### 8.2 端到端手工 QA（跨 session 5 阶段全流程）

1. 启动 dev 环境（`./dev.sh`）
2. 用 dev-auth-bypass token 进入 `/coach`，初始 stage = `prepare`
3. 选择"AI Agent 工程师" → 进入 `/interview`（stage 转 `interview`）
4. 跑完 5 轮面试 → 收尾（stage 转 `coach`）
5. 回到 `/coach`，点击"让教练复盘"
   - 验证 SSE 流式渲染复盘文本
   - 验证 plan_done 后展示训练计划卡片
   - 验证 DB 中 `coach_plans` 行已写入，且 `consumed=false`
6. 开启第二场面试
   - 验证 prepare 阶段的开场词引用了第一场的 weakness（如"上次量化分 2.1，今天目标 3.0+"）
   - 验证 LangGraph state 的 candidate_profile 初始化时从 candidate_memory 读取（跨 session 记忆生效）

### 8.3 总结与风险报告
落档 `docs/superpowers/qa-reports/phase5-qa-report.md`，参考 Phase 4+ 格式：
- 已改动文件清单
- 测试新增/修改条数
- 真实 QA 结果
- 已知风险与遗留 TODO（含本期没做的 Vector DB 检索、对话式 coach 等）

### 8.4 提议 commit 序列
按 conventional commits 拆 7 个 commit（每步一个，与 Step 1-7 一一对应）；Step 8 单独一个 docs commit：

```
1. feat(db): add candidate_memory and coach_plans tables
2. feat(coach): add candidate_memory upsert service
3. feat(interviewer): persist candidate profile to memory on report
4. feat(coach): derive user stage from session and plan state
5. feat(coach): add coach langgraph subgraph with review and plan nodes
6. feat(coach): add coach review sse endpoint and latest plan getter
7. feat(frontend): add coach review plan card and stage-aware cta
8. docs: add phase 5 qa report
```

---

## 执行顺序总览

| Step | 范围 | 测试 | 风险 | 用户确认点 |
|------|------|------|------|-----------|
| 1 | DB schema + Alembic | 3 单测 + 1 集成 | 中 | commit |
| 2 | candidate_memory upsert service | 4 单测 | 低 | commit |
| 3 | interviewer report_node 接入 | 2 单测 | 中 | commit |
| 4 | user stage 派生 + endpoint | 4 单测 + 1 集成 | 低 | commit |
| 5 | coach LangGraph 子图 | 5 单测 | 中 | commit |
| 6 | coach SSE endpoint | 4 集成 | 中 | commit |
| 7 | 前端 plan card + stage CTA | 4 vitest | 低 | commit |
| 8 | 全套验证 + QA + 报告 | 所有 | — | 总结 |

总预估：**2-3 个工作日**（含测试 + review + commit gate）。

---

## 不做的事（明确边界）

- 不动 interviewer / prepare graph 拓扑
- 不引入 Vector DB（Q6 已确认延后）
- 不做对话式 coach（Q5 已确认延后）
- 不写持久化 `current_stage` 字段（Q4 已确认派生函数）
- 不做 LLM-as-Judge 评估 coach 输出（Phase 6 范围）
- 不动 `coach_opening.py` 主逻辑（仅可能小幅引用 plan 字段）
- 不重构 `/reports` / `/dashboard` / `/settings`

---

## 后续 Phase 6+ 衍生项（仅记录，不实施）

- LLM-as-Judge 评估 coach plan 质量
- Vector DB 检索"相似候选人" / 相似 weakness pattern
- 对话式 coach（多轮咨询）
- coach 主动 push（邮件 / 站内信）
- weakness_events 拆表 + session 级 trace 引证
