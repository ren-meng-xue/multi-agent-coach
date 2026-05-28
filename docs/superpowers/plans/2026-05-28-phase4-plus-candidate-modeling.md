# Phase 4+ 实施 Plan（按 TDD 分步）

**对应 Spec**：`docs/superpowers/specs/2026-05-28-phase4-plus-candidate-modeling-design.md`
**目标**：候选人建模 + latent signals + 追问策略，分 6 个可独立验证的小步落地，每步先写失败测试再实现。

---

## 总体策略

- **TDD**：每步先写/扩展失败测试，再实现，再跑测试。
- **小步可回滚**：每步独立 commit（等待用户确认后才 commit）。
- **不并行改 graph 拓扑**：所有改动是 prompt + state 字段 + Pydantic schema 追加。
- **mock LLM**：不调真实 OpenAI，所有测试用 `unittest.mock.AsyncMock` mock `_evaluator_score / _master_phase2_decide / _generate_text`。
- **验证命令**（每步实现后跑）：
  - 后端：`cd backend && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy app && .venv/bin/python -m pytest tests/unit/test_interviewer_*.py`
  - 前端：`cd frontend && pnpm test -- trace-node interview-chat && pnpm typecheck`
- **完整验证留到最后一步**：避免中间步骤 build 慢拖累迭代。

---

## Step 1 · State / Pydantic schema 扩展（地基）

**目标**：让 TypedDict 与 Pydantic schema 接受新字段，**不动节点逻辑**。

### 1.1 改动文件
- `backend/app/agents/interviewer/state.py`
  - `TurnEvaluation` 加 `candidate_level / latent_signals / missing_dimensions`（可选）
  - 新建 `CandidateProfile` TypedDict
  - `InterviewState` 加 `candidate_profile / followup_focus`
- `backend/app/agents/interviewer/nodes.py`
  - `_EvaluatorScoring` 加新字段（默认值）
  - `_InterviewMasterDecision` 加 `followup_focus`

### 1.2 失败测试（新增）

`backend/tests/unit/test_interviewer_evaluator_node.py` 末尾追加：

```python
def test_turn_evaluation_accepts_new_optional_fields():
    from app.agents.interviewer.state import TurnEvaluation
    entry: TurnEvaluation = {
        "question_index": 1,
        "candidate_level": "junior",
        "latent_signals": ["workflow_orchestration"],
        "missing_dimensions": ["quantification"],
    }
    assert entry["candidate_level"] == "junior"
    assert entry["latent_signals"] == ["workflow_orchestration"]


def test_evaluator_scoring_defaults_new_fields():
    from app.agents.interviewer.nodes import _EvaluatorScoring
    s = _EvaluatorScoring()
    assert s.candidate_level == "junior"
    assert s.latent_signals == []
    assert s.missing_dimensions == []
```

`backend/tests/unit/test_interviewer_master_node.py` 末尾追加：

```python
def test_master_decision_defaults_followup_focus():
    from app.agents.interviewer.nodes import _InterviewMasterDecision
    d = _InterviewMasterDecision()
    assert d.followup_focus == ""
```

### 1.3 验证
- 新测试先失败（字段不存在 / Pydantic 抛错）
- 实现后跑 `pytest tests/unit/test_interviewer_evaluator_node.py tests/unit/test_interviewer_master_node.py`，全绿
- `ruff check` + `mypy app/agents/interviewer/`

### 1.4 风险
- 极低。纯字段追加。

### 1.5 检查点
- 给用户报"Step 1 done，是否 commit"

---

## Step 2 · evaluator 跨轮上下文 + 写画像

**目标**：`_build_evaluator_context` 改为读最近 8 条消息 + 候选人画像；`evaluator_node` 把 latent_signals / candidate_level 写入 `turn_evaluations[-1]` 和 `candidate_profile`。

### 2.1 改动文件
- `backend/app/agents/interviewer/nodes.py`
  - `_build_evaluator_context` 重写
  - `evaluator_node` 写入新字段 + `candidate_profile`

### 2.2 失败测试（新增到 `test_interviewer_evaluator_node.py`）

```python
@pytest.mark.asyncio
async def test_evaluator_uses_last_n_messages_in_context():
    """超出 8 条时只保留最近 8 条。"""
    messages = []
    for i in range(20):
        messages.append(HumanMessage(content=f"user msg {i}"))
        messages.append(AIMessage(content=f"ai msg {i}"))
    state = {
        "question_count": 2,
        "messages": messages,
        "turn_evaluations": [],
    }
    captured = {}
    async def fake_score(context: str):
        captured["context"] = context
        return MagicMock(
            bullets=[], technical_depth=5, quantified_results=5,
            failure_tradeoffs=5, structure=5, summary_score=5,
            candidate_level="junior", latent_signals=[], missing_dimensions=[],
        )
    with patch("app.agents.interviewer.nodes._evaluator_reason_stream", new=AsyncMock()), \
         patch("app.agents.interviewer.nodes._evaluator_score", new=AsyncMock(side_effect=fake_score)):
        await evaluator_node(state)
    # 最早的 user msg 0 不应该出现在 context 里
    assert "user msg 0" not in captured["context"]
    # 最新的 user msg 19 应该出现
    assert "user msg 19" in captured["context"]


@pytest.mark.asyncio
async def test_evaluator_writes_candidate_profile():
    fake_scoring = MagicMock(
        bullets=[], technical_depth=5, quantified_results=5,
        failure_tradeoffs=5, structure=5, summary_score=5,
        candidate_level="junior",
        latent_signals=["workflow_orchestration", "event_driven_architecture"],
        missing_dimensions=["quantification"],
    )
    state = {
        "question_count": 1,
        "messages": [],
        "turn_evaluations": [],
        "candidate_profile": {},
    }
    with patch("app.agents.interviewer.nodes._evaluator_reason_stream", new=AsyncMock()), \
         patch("app.agents.interviewer.nodes._evaluator_score", new=AsyncMock(return_value=fake_scoring)):
        result = await evaluator_node(state)
    last = result["turn_evaluations"][-1]
    assert last["candidate_level"] == "junior"
    assert "workflow_orchestration" in last["latent_signals"]
    assert "quantification" in last["missing_dimensions"]
    profile = result["candidate_profile"]
    assert profile["latest_level"] == "junior"
    assert set(profile["latent_signals"]) == {"workflow_orchestration", "event_driven_architecture"}


@pytest.mark.asyncio
async def test_evaluator_accumulates_signals_dedup_ordered():
    """连续两轮的 latent_signals 去重保序累积。"""
    fake_scoring = MagicMock(
        bullets=[], technical_depth=5, quantified_results=5,
        failure_tradeoffs=5, structure=5, summary_score=5,
        candidate_level="mid",
        latent_signals=["b", "c"],
        missing_dimensions=[],
    )
    state = {
        "question_count": 2,
        "messages": [],
        "turn_evaluations": [],
        "candidate_profile": {"latent_signals": ["a", "b"], "latest_level": "junior"},
    }
    with patch("app.agents.interviewer.nodes._evaluator_reason_stream", new=AsyncMock()), \
         patch("app.agents.interviewer.nodes._evaluator_score", new=AsyncMock(return_value=fake_scoring)):
        result = await evaluator_node(state)
    assert result["candidate_profile"]["latent_signals"] == ["a", "b", "c"]
    assert result["candidate_profile"]["latest_level"] == "mid"  # 用最新值
```

### 2.3 验证
- 现有 3 个 evaluator 测试要继续通过（向后兼容）
- 3 个新测试要通过
- `pytest tests/unit/test_interviewer_evaluator_node.py`

### 2.4 风险
- 现有测试里 `fake_scoring` MagicMock 默认会"凭空生成"任何属性 → 旧测试不会因为读 `candidate_level` 报错。需要确认 `evaluator_node` 实现里访问新字段时用 `getattr(..., default)` 或确认 MagicMock 行为。

### 2.5 检查点
- "Step 2 done，是否 commit"

---

## Step 3 · master 输出 followup_focus + 上下文加画像

**目标**：`master_node` 把候选人画像塞进 context；`_master_phase2_decide` 返回 `followup_focus`，写入 state。

### 3.1 改动文件
- `backend/app/agents/interviewer/nodes.py`
  - `_build_master_context` 增加画像信息
  - `master_node` 把 `decision.followup_focus` 写入 state
- `backend/app/agents/interviewer/prompts.py`
  - `MASTER_DECISION_PROMPT` 追加 `followup_focus` 输出说明

### 3.2 失败测试

`backend/tests/unit/test_interviewer_master_node.py` 追加：

```python
@pytest.mark.asyncio
async def test_master_writes_followup_focus_to_state():
    from app.agents.interviewer.nodes import master_node
    fake_decision = MagicMock(
        chain=["evaluator", "followup"],
        reason="深挖架构",
        followup_focus="architecture",
    )
    state = {
        "question_count": 1,  # 非首轮
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [HumanMessage(content="我用了 Redis 做缓存")],
        "candidate_profile": {"latest_level": "junior", "latent_signals": ["caching"]},
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock()), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["followup_focus"] == "architecture"
    assert result["chain"] == ["evaluator", "followup"]


@pytest.mark.asyncio
async def test_master_context_contains_candidate_profile():
    from app.agents.interviewer.nodes import master_node
    captured = {}
    fake_decision = MagicMock(chain=["evaluator", "followup"], reason="", followup_focus="")
    async def fake_decide(context: str):
        captured["context"] = context
        return fake_decision
    state = {
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [HumanMessage(content="我处理事件流")],
        "candidate_profile": {
            "latest_level": "beginner",
            "latent_signals": ["workflow_orchestration"],
        },
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock()), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(side_effect=fake_decide)):
        await master_node(state)
    assert "beginner" in captured["context"]
    assert "workflow_orchestration" in captured["context"]
```

### 3.3 验证
- 现有 master 测试通过（chain 合法性约束没改）
- 新测试通过

### 3.4 检查点
- "Step 3 done，是否 commit"

---

## Step 4 · followup 消费 focus + signals

**目标**：`followup_node` 在 prompt 里注入 `followup_focus / latent_signals / missing_dimensions`；新 `FOLLOWUP_SYSTEM_PROMPT`。

### 4.1 改动文件
- `backend/app/agents/interviewer/prompts.py`
  - 重写 `FOLLOWUP_SYSTEM_PROMPT`
- `backend/app/agents/interviewer/nodes.py`
  - `followup_node` 在 system prompt 后追加 `extra_ctx`

### 4.2 失败测试（新增到 `test_interviewer_evaluator_node.py` 或新建 `test_interviewer_followup_node.py`）

```python
@pytest.mark.asyncio
async def test_followup_injects_focus_and_signals_into_prompt():
    from app.agents.interviewer.nodes import followup_node
    captured = {}
    async def fake_generate(system_prompt: str, state):
        captured["prompt"] = system_prompt
        return "针对 event lifecycle 的追问"
    state = {
        "followup_count": 0,
        "messages": [HumanMessage(content="不知道事件流")],
        "followup_focus": "latent_signal:workflow_orchestration",
        "turn_evaluations": [
            {
                "latent_signals": ["workflow_orchestration", "event_driven_architecture"],
                "missing_dimensions": ["architecture"],
            }
        ],
    }
    with patch("app.agents.interviewer.nodes._generate_text", new=AsyncMock(side_effect=fake_generate)):
        result = await followup_node(state)
    assert "workflow_orchestration" in captured["prompt"]
    assert "architecture" in captured["prompt"]
    assert "followup_focus" in captured["prompt"]
    assert result["assistant_message"] == "针对 event lifecycle 的追问"
    assert result["followup_count"] == 1


@pytest.mark.asyncio
async def test_followup_works_without_focus_or_signals():
    """无 focus / 无 signals 时不崩，行为退化到原版。"""
    from app.agents.interviewer.nodes import followup_node
    state = {
        "followup_count": 0,
        "messages": [HumanMessage(content="...")],
    }
    with patch("app.agents.interviewer.nodes._generate_text", new=AsyncMock(return_value="ok")):
        result = await followup_node(state)
    assert result["assistant_message"] == "ok"
    assert result["followup_count"] == 1
```

### 4.3 验证
- 现有 followup 行为相关的测试（如果有）继续通过
- 新测试通过

### 4.4 检查点
- "Step 4 done，是否 commit"

---

## Step 5 · SSE 透传 + 前端渲染

**目标**：把新字段从后端 graph 透传到前端，trace-node 追加渲染。

### 5.1 改动文件
- `backend/app/agents/interviewer/graph.py`
  - evaluator `node_done` payload 加 `candidate_level / latent_signals / missing_dimensions`
  - master `node_done` payload 加 `followup_focus`
- `frontend/lib/prepare-types.ts`（或对应类型文件）
  - `InterviewTraceNodeEvent` 加可选字段
  - `TraceNodeData` 加 `candidateLevel / latentSignals / missingDimensions`
- `frontend/app/interview/_components/interview-chat.tsx`
  - `updateTurnTrace` 在 `phase === "done"` 时合并新字段（只在 evaluator/master 各自的分支里）
- `frontend/app/interview/_components/trace-node.tsx`
  - props 加新字段
  - evaluator + done 时追加渲染 chips 区域

### 5.2 失败测试

后端 `tests/unit/test_interviewer_graph.py`（扩展或新建）：

```python
# 验证 stream_interviewer_turn_events 的 evaluator node_done payload 含新字段
# 这部分原本就 mock graph，扩展现有断言即可
```

前端 `trace-node.test.tsx` 追加：

```tsx
it("evaluator done with latent signals 渲染 chips", () => {
  render(
    <TraceNode
      id="evaluator"
      label="评估官"
      title="多维深度评估"
      status="done"
      tokens=""
      candidateLevel="junior"
      latentSignals={["workflow_orchestration", "state_management"]}
      missingDimensions={["quantification"]}
    />
  );
  expect(screen.getByText(/junior/i)).toBeInTheDocument();
  expect(screen.getByText("workflow_orchestration")).toBeInTheDocument();
  expect(screen.getByText(/缺失：quantification/)).toBeInTheDocument();
});

it("evaluator done 无新字段时不渲染额外块", () => {
  const { queryByText } = render(
    <TraceNode id="evaluator" label="评估官" title="x" status="done" tokens="" />
  );
  expect(queryByText(/缺失/)).toBeNull();
});
```

前端 `interview-chat.test.tsx` 追加 SSE 解析新字段 → `TraceNodeData` 合并的断言。

### 5.3 验证
- 后端 graph 测试通过
- 前端 `pnpm test -- trace-node interview-chat`
- 前端 `pnpm typecheck`

### 5.4 风险
- `interview-chat.tsx` 是 930 行的大文件，改动局限在 `updateTurnTrace` 函数内部，~20 行追加即可。

### 5.5 检查点
- "Step 5 done，是否 commit"

---

## Step 6 · 完整验证 + 文档对账

### 6.1 跑全套验证
```bash
cd backend && .venv/bin/python -m ruff check .
cd backend && .venv/bin/python -m mypy app
cd backend && .venv/bin/python -m pytest tests/

cd frontend && pnpm test
cd frontend && pnpm typecheck
cd frontend && pnpm build
```

### 6.2 手工 QA（按 Spec §1.2 真实脚本）
- 启动 dev 环境（`./dev.sh`）
- 用 dev-auth-bypass token 进入 `/interview`
- 输入 Spec §1.2 那段"不知道事件流 / 用 Claude / 用 Codex"的真实回答
- 验证：
  - evaluator 节点 trace 卡里出现 `junior` / `beginner` badge
  - latent_signals chips 至少出现 `workflow_orchestration` 或同类信号
  - followup 不再追问"为什么选 GPT 5.5 / 参数怎么调"
  - followup 转而问"event lifecycle 怎么管理 / 三类事件怎么统一"之类

### 6.3 总结与风险报告
向用户报告：
- 已改动文件清单
- 测试新增/修改条数
- 真实 QA 结果（截图或对话记录）
- 已知风险与遗留 TODO

### 6.4 提议 commit 序列
按 conventional commits 拆 5 个 commit（每步一个）：
1. `feat(interviewer): extend state with candidate_profile and followup_focus`
2. `feat(interviewer): evaluator emits candidate_level and latent_signals`
3. `feat(interviewer): master decides followup_focus from candidate profile`
4. `feat(interviewer): followup consumes focus and latent signals`
5. `feat(frontend): render candidate_level and latent_signals on evaluator trace node`

或合并成 2-3 个 commit（后端 / 前端 / 测试），由用户决定。

---

## 执行顺序总览

| Step | 范围 | 测试 | 风险 | 用户确认点 |
|------|------|------|------|-----------|
| 1 | State + Pydantic schema | 3 个 schema 单测 | 极低 | commit |
| 2 | evaluator 跨轮 + 写画像 | 3 个 evaluator 单测 | 低 | commit |
| 3 | master 输出 focus | 2 个 master 单测 | 低 | commit |
| 4 | followup 消费 focus | 2 个 followup 单测 | 低 | commit |
| 5 | SSE + 前端渲染 | 2-3 个前端单测 | 中（前端文件大） | commit |
| 6 | 全套验证 + QA | 所有 | — | 总结 |

总预估：4-6 小时（含测试）。

---

## 不做的事（明确边界）

- 不动 graph 拓扑、不动 DB schema、不写 Alembic 迁移
- 不引入新节点 / 新 Agent
- 不动 Coach 开场词、report_node、closing_node 逻辑
- 不写 e2e Playwright 测试
- 不做跨 session candidate model 累积（留给第 5 步）
- 不动 prompt 之外的"廉价赞美 / 客观反馈"等已有准则
