# Prepare Parallel + Research Agent Review Fix Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Keep changes scoped to the three review findings below.

**Goal:** 修复 Prepare 阶段 review 中指出的 3 个 P2 问题：`memory_search` 与 `research_agent` 真并行 fan-out、`research_agent` 工具调用遵守 90 秒总预算、非超时外部调用异常降级到 JD 分析兜底。

**Architecture:** 保持现有 Prepare Graph + Supervisor Loop 架构，但把第一轮可并行的 I/O 节点从“Supervisor 串行选择下一个节点”改为 graph-level fan-out：当存在可查记忆且有 JD 时，Supervisor 一次性调度 `memory_search` 与 `research_agent`，两个节点完成后再汇合回 Supervisor。`research_agent` 内部统一用剩余总预算控制 LLM 与工具调用，所有外部调用异常记录 warning 并返回 `job_intel=None`，让 Supervisor 继续走 `jd_analysis`。

**Tech Stack:** Python 3.12 / LangGraph / LangChain / pytest / ruff

---

## Review Findings

| Severity | File | Problem |
|---|---|---|
| P2 | `backend/app/agents/prepare/graph.py` | `_supervisor_router` 只返回单个节点，`memory_search` / `research_agent` 串行执行，未满足真并行 fan-out |
| P2 | `backend/app/agents/prepare/research_agent.py` | 每个 tool call 固定 30 秒，没有扣减 `TOTAL_TIMEOUT_SECONDS` 剩余预算 |
| P2 | `backend/app/agents/prepare/research_agent.py` | 非 `TimeoutError` 的 LLM / MCP 异常会冒泡，导致 Prepare SSE 失败 |

---

## Design Decisions

### 1. 并行范围只覆盖首轮独立 I/O

`memory_search` 与 `research_agent` 可以并行；`jd_analysis` 和 `question_gen` 不并行：

- `memory_search`：读取历史薄弱点和简历摘要兜底。
- `research_agent`：基于当前输入 JD / 背景做岗位调研。
- `jd_analysis`：仅在 `research_agent` 完成但 `job_intel=None` 后作为 fallback。
- `question_gen`：必须等历史薄弱点、岗位情报或 JD 分析完成后再生成题目。

### 2. 并行后的状态合并必须显式处理

两个并行节点都会追加 `completed_tools`，不能依赖普通 list 覆盖合并。需要确保并行汇合后的状态包含：

- `completed_tools` 同时包含 `memory_search` 和 `research_agent`。
- `weak_areas` / `user_background` 来自 `memory_search`。
- `job_intel` 来自 `research_agent`，失败时为 `None`。

如 LangGraph 当前 state reducer 不支持 list 合并，应新增小型 reducer 或改为汇合节点统一去重合并，避免丢状态。

### 3. Research Agent 总预算是硬上限

`TOTAL_TIMEOUT_SECONDS=90` 是整个 `research_agent_node` 的总预算，不是单个 LLM 或工具调用预算。每次外部调用前重新计算剩余时间：

- 剩余时间 `<= 0`：停止 loop，进入已有 finalize / fallback。
- LLM 调用 timeout 使用剩余预算。
- tool 调用 timeout 使用 `min(30, remaining_budget)`，不能额外增加 30 秒。
- `_force_finalize` 也必须遵守剩余预算；预算不足时直接返回 `None`。

### 4. 异常降级但不静默

以下异常路径都应记录 warning，然后降级：

- `model.ainvoke(...)` 抛出 `TimeoutError`、OpenAI retryable error、网络错误或其他非致命异常。
- `tool.ainvoke(...)` 抛出异常。
- `_force_finalize(...)` 抛出异常或预算不足。

降级结果统一为 `job_intel=None`，并追加 `completed_tools=["research_agent"]`，让 Supervisor 继续进入 `jd_analysis`。

---

## File Map

| Path | Change |
|---|---|
| `backend/app/agents/prepare/graph.py` | 改 fan-out 路由 / 汇合行为，保证 `memory_search` 与 `research_agent` 可重叠执行 |
| `backend/app/agents/prepare/state.py` | 如需要，给并行状态字段补 reducer 类型定义 |
| `backend/app/agents/prepare/research_agent.py` | 加剩余预算 helper，工具和 finalize 统一扣减总预算，外层异常降级 |
| `backend/tests/unit/test_prepare_graph.py` | 补并行 fan-out / 状态合并回归测试 |
| `backend/tests/unit/test_research_agent.py` | 补总预算和非超时异常降级测试；如文件不存在则新建 |

---

## Task 1: Research Agent 总预算修复

**Files:**

- Modify: `backend/app/agents/prepare/research_agent.py`
- Create/Modify: `backend/tests/unit/test_research_agent.py`

- [ ] Step 1.1: 新增预算 helper

实现一个局部 helper，例如：

```python
def _remaining_budget_seconds(started: float) -> float:
    return max(0.0, TOTAL_TIMEOUT_SECONDS - (time.time() - started))
```

调用外部 API 前统一使用该 helper。

- [ ] Step 1.2: LLM 调用使用剩余预算

把 `model.ainvoke(messages)` 的 `wait_for` timeout 改为当前剩余预算；预算不足时跳出 loop。

- [ ] Step 1.3: Tool 调用使用 `min(30, remaining)`

每个 tool call 前重新计算剩余时间。剩余时间不足时记录 `research_agent_budget_exhausted_before_tool`，停止继续调用本轮剩余 tools。

- [ ] Step 1.4: `_force_finalize` 遵守剩余预算

给 `_force_finalize` 增加 timeout 参数，调用方传入剩余预算；预算不足时不调用 `generate_position_report`。

- [ ] Step 1.5: 单测覆盖

测试点：

- 多个慢 tool call 不会突破 90 秒总预算。
- 剩余预算低于 30 秒时，tool timeout 使用剩余预算。
- finalize 不会在预算耗尽后继续额外等待。

---

## Task 2: Research Agent 异常降级修复

**Files:**

- Modify: `backend/app/agents/prepare/research_agent.py`
- Create/Modify: `backend/tests/unit/test_research_agent.py`

- [ ] Step 2.1: 扩大外层异常捕获

外层 ReAct loop 捕获 `TimeoutError` 和普通 `Exception`，但必须记录 warning，日志里包含 `error` 和 `elapsed_ms`。

- [ ] Step 2.2: 保持 fallback contract

发生非超时异常后不抛出到 SSE；继续尝试 `_extract_final_report` / `_force_finalize`。如果仍没有报告，返回：

```python
{**state, "job_intel": None, "completed_tools": completed + ["research_agent"]}
```

- [ ] Step 2.3: 单测覆盖

测试点：

- `model.ainvoke(...)` 抛 `RuntimeError` / APIConnectionError 风格异常时，节点返回 `job_intel=None`。
- 异常路径仍追加 `completed_tools`。
- 异常不会向外冒泡。

---

## Task 3: Prepare Graph 真并行 fan-out

**Files:**

- Modify: `backend/app/agents/prepare/graph.py`
- Modify: `backend/app/agents/prepare/state.py` if reducer needed
- Modify: `backend/tests/unit/test_prepare_graph.py`

- [ ] Step 3.1: 明确 fan-out 条件

当 Supervisor 判断 Prepare 已有方向且：

- `memory_search` 未完成；
- 有 `jd_raw` 或 `jd_url` 且 `research_agent` 未完成；

则同一轮 fan-out 到 `memory_search` 和 `research_agent`。

如果只有一个条件成立，则仍只调度对应单节点。

- [ ] Step 3.2: 改 router 返回多目标

把当前 `_supervisor_router(state) -> str` 扩展为能返回多个目标的 conditional edge path。优先使用 LangGraph 原生多边返回；如果当前版本不支持，新增显式并行入口节点。

- [ ] Step 3.3: 处理并行状态合并

确保汇合后：

- `completed_tools` 去重保序；
- `weak_areas` 不被 `research_agent` 的旧 state 覆盖；
- `job_intel` 不被 `memory_search` 的旧 state 覆盖；
- `user_background` 使用 `memory_search` 补到的值，除非原始输入已有背景。

- [ ] Step 3.4: 保持 fallback 顺序

并行完成后回到 Supervisor：

- `research_agent` 成功：跳过 `jd_analysis`，进入 `question_gen`。
- `research_agent` 失败且有 JD：进入 `jd_analysis`。
- 没有 JD：跳过 `research_agent` / `jd_analysis`，进入 `question_gen`。

- [ ] Step 3.5: 单测覆盖

测试点：

- 同时有用户和 JD 时，graph 会调度 `memory_search` 与 `research_agent` 两个节点。
- 两个节点完成后的 state 同时包含 `weak_areas` 和 `job_intel`。
- `research_agent` 返回 `job_intel=None` 时，后续进入 `jd_analysis`。
- SSE 事件中两个节点都能发 `node_start` / `node_done`，不会被 `finished_nodes` 误吞。

---

## Task 4: 验证

**Commands:**

```bash
cd backend
uv run pytest tests/unit/test_research_agent.py tests/unit/test_prepare_graph.py -v
uv run ruff check app/agents/prepare tests/unit/test_research_agent.py tests/unit/test_prepare_graph.py
```

如改到 `PrepareState` 类型 reducer 或 TypedDict 结构，再追加：

```bash
cd backend
uv run mypy app/agents/prepare
```

---

## Acceptance Criteria

- [ ] `memory_search` 与 `research_agent` 在同时满足条件时由 graph 同轮 fan-out，不再依赖 Supervisor 串行二次调度。
- [ ] 并行汇合后的 final state 不丢 `completed_tools`、`weak_areas`、`user_background`、`job_intel`。
- [ ] `research_agent_node` 所有 LLM / tool / finalize 调用共同遵守 `TOTAL_TIMEOUT_SECONDS=90`。
- [ ] `model.ainvoke(...)` 非超时异常不会打断 Prepare SSE，而是降级为 `job_intel=None`。
- [ ] `job_intel=None` 后 Supervisor 能继续走 `jd_analysis` 兜底。
- [ ] 相关单测和 ruff 通过。

---

## Risk Notes

- 并行后 `research_agent` 可能无法消费 `memory_search` 补到的简历摘要；这是并行化带来的预期取舍。若产品要求岗位调研必须结合简历摘要，应把简历摘要读取拆成更早的轻量 preload，或者接受 `research_agent` 只使用用户显式提供的背景。
- LangGraph 并行 state 合并是本计划最大风险点，必须用回归测试锁住，不要只看 trace。
