# research_agent 工具级 ReAct Trace 可视化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让前端 trace panel 中 `research_agent` 节点能展开，呈现 ReAct 步骤树（多轮 iteration、流式 think、按工具卡片化的 tool_call / observe），把"Agent 工具思考接入 MCP"的过程可视化给用户。

**Architecture:** 后端在 `research_agent_node` ReAct loop 各步骤通过 LangGraph `astream_writer` emit 5 类工具级 SSE 事件；`stream_prepare_events` 把这些自定义事件转换为前端约定格式；前端在 SSE handler 里按 `step_id` 聚合成 `ReactIteration[]`，扩展 `TraceNode` 渲染嵌套 `ReactStepTree` 组件，含折叠/展开逻辑。

**Tech Stack:** Python 3.12 / LangGraph 1.x（`astream_writer`）/ FastAPI SSE / Next.js / React / TypeScript / Tailwind CSS / Vitest / Testing Library

**Spec 文档:** `docs/superpowers/specs/2026-06-03-react-tool-trace-visualization-design.md`

**前置依赖:** 必须先合入 `feature/research-agent-mcp` 分支（research_agent 节点已存在并跑通）。本 plan 在 `feature/react-tool-trace-viz` 分支上执行。

---

## File Structure

### 后端（multi-agent-coach）

| 操作   | 路径                                             | 职责                                                                        |
| ------ | ------------------------------------------------ | --------------------------------------------------------------------------- |
| Modify | `backend/app/agents/prepare/research_agent.py`   | ReAct loop 各步 emit 自定义事件；加 `_summarize_args` / `_summarize_result` |
| Modify | `backend/app/agents/prepare/graph.py`            | `stream_prepare_events` 处理 `on_custom` 事件分支                           |
| Modify | `backend/tests/unit/test_research_agent.py`      | 加 emit 验证测试                                                            |
| Create | `backend/tests/unit/test_research_agent_emit.py` | 独立的 emit 行为测试                                                        |

### 前端（multi-agent-coach）

| 操作   | 路径                                                          | 职责                                                       |
| ------ | ------------------------------------------------------------- | ---------------------------------------------------------- |
| Modify | `frontend/lib/prepare-types.ts`                               | 加事件枚举、新字段、`ReactIteration` / `ToolCallStep` 类型 |
| Modify | `frontend/app/interview/_components/interview-chat.tsx`       | SSE handler 加新事件分支，聚合到 `reactSteps`              |
| Modify | `frontend/app/interview/_components/trace-node.tsx`           | 加 `reactSteps` prop + 展开/折叠 + 嵌入 ReactStepTree      |
| Modify | `frontend/app/interview/_components/trace-node.test.tsx`      | 加折叠/展开 + reactSteps 渲染用例                          |
| Create | `frontend/app/interview/_components/tool-call-card.tsx`       | 单个工具调用卡片                                           |
| Create | `frontend/app/interview/_components/tool-call-card.test.tsx`  | 状态切换 / 错误显示用例                                    |
| Create | `frontend/app/interview/_components/react-step-tree.tsx`      | ReactStepTree + IterationGroup                             |
| Create | `frontend/app/interview/_components/react-step-tree.test.tsx` | 流式累积 / 多轮渲染用例                                    |

---

## Phase 1 — 后端 SSE emit

### Task 1: 加 `_summarize_args` / `_summarize_result` 辅助函数

**Files:**

- Modify: `backend/app/agents/prepare/research_agent.py`
- Create: `backend/tests/unit/test_research_agent_emit.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_research_agent_emit.py`：

```python
"""research_agent 工具级 emit / 摘要辅助函数测试。"""
from __future__ import annotations

import pytest


def test_summarize_args_truncates_long_strings():
    from app.agents.prepare.research_agent import _summarize_args
    result = _summarize_args({"text": "x" * 100, "max_results": 5})
    assert "text=" in result
    assert "..." in result
    assert "max_results=5" in result


def test_summarize_args_describes_lists_and_dicts():
    from app.agents.prepare.research_agent import _summarize_args
    result = _summarize_args({"items": [1, 2, 3], "extra": {"a": 1, "b": 2}})
    assert "items=<list len=3>" in result
    assert "extra=<dict len=2>" in result


def test_summarize_result_for_dict_lists_keys():
    from app.agents.prepare.research_agent import _summarize_result
    result = _summarize_result({"title": "x", "company": "y", "requirements": []})
    assert "title" in result and "company" in result and "requirements" in result
    assert result.startswith("{") and result.endswith("}")


def test_summarize_result_for_list_shows_count():
    from app.agents.prepare.research_agent import _summarize_result
    result = _summarize_result([{"a": 1}, {"a": 2}, {"a": 3}])
    assert result == "[3 条结果]"


def test_summarize_result_truncates_long_string():
    from app.agents.prepare.research_agent import _summarize_result
    result = _summarize_result("x" * 200)
    assert result.endswith("...")
    assert len(result) <= 130
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend
uv run pytest tests/unit/test_research_agent_emit.py -v
```

预期：5 条 FAIL（`ImportError`）

- [ ] **Step 3: 加辅助函数**

在 `backend/app/agents/prepare/research_agent.py` 文件顶部 import 区下、`research_agent_node` 函数之前追加：

```python
def _summarize_args(args: dict) -> str:
    """工具入参摘要：截短长字符串、隐藏 list/dict 内容，前端可直接展示。"""
    parts: list[str] = []
    for k, v in (args or {}).items():
        if isinstance(v, str):
            v_short = v[:60] + ("..." if len(v) > 60 else "")
            parts.append(f'{k}="{v_short}"')
        elif isinstance(v, list):
            parts.append(f"{k}=<list len={len(v)}>")
        elif isinstance(v, dict):
            parts.append(f"{k}=<dict len={len(v)}>")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def _summarize_result(result) -> str:
    """工具出参摘要：dict 列 key、list 给计数、string 截短。"""
    if isinstance(result, dict):
        keys = list(result.keys())[:6]
        body = ", ".join(keys)
        suffix = "..." if len(result) > 6 else ""
        return "{" + body + "}" + suffix
    if isinstance(result, list):
        return f"[{len(result)} 条结果]"
    if isinstance(result, str):
        if len(result) > 120:
            return result[:120] + "..."
        return result
    s = str(result)
    return s[:120] + ("..." if len(s) > 120 else "")
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/unit/test_research_agent_emit.py -v
```

预期：5 条 PASS

- [ ] **Step 5: commit**

```bash
git add backend/app/agents/prepare/research_agent.py backend/tests/unit/test_research_agent_emit.py
git commit -m "feat(research_agent): 加 _summarize_args / _summarize_result 摘要辅助"
```

---

### Task 2: ReAct loop 在每一步 emit 工具级事件

**Files:**

- Modify: `backend/app/agents/prepare/research_agent.py`
- Modify: `backend/tests/unit/test_research_agent_emit.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_research_agent_emit.py` 追加：

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage


def _mock_tool(name: str, return_value):
    t = MagicMock()
    t.name = name
    t.ainvoke = AsyncMock(return_value=return_value)
    return t


@pytest.mark.asyncio
async def test_research_agent_emits_full_react_step_sequence():
    """ReAct loop 应按 think_start → think_token* → think_done → tool_call_start → tool_call_done 顺序 emit。"""
    from app.agents.prepare.research_agent import research_agent_node

    fake_report = {
        "job_interpretation": {}, "resume_match": {},
        "company_profile": {}, "interview_qa": [],
        "salary_range": {}, "prep_suggestions": [],
    }
    tools = [_mock_tool("generate_position_report", fake_report)]

    # 第 1 轮：LLM streaming 吐两个 chunk 然后调 generate_position_report
    chunk1 = MagicMock(); chunk1.content = "我先调研"
    chunk2 = MagicMock(); chunk2.content = "目标岗位"
    msg = AIMessage(
        content="我先调研目标岗位",
        tool_calls=[{
            "name": "generate_position_report",
            "args": {"title": "后端", "company": "字节", "jd_summary": "...",
                     "requirements": [], "search_results": {}, "directions": ["x"]},
            "id": "c1",
        }],
    )
    stop_msg = AIMessage(content="完成")

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)

    async def astream_side(messages):
        for c in [chunk1, chunk2]:
            yield c

    mock_model.astream = astream_side
    mock_model.ainvoke = AsyncMock(side_effect=[msg, stop_msg])

    emitted: list[dict] = []

    def fake_writer(payload):
        emitted.append(payload)

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=tools),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
        patch("app.agents.prepare.research_agent.get_stream_writer", return_value=fake_writer),
    ):
        await research_agent_node(state)

    kinds = [e.get("kind") for e in emitted]
    # 至少应包含完整一轮的事件序列
    assert "tool_thinking_start" in kinds
    assert "tool_thinking_token" in kinds
    assert "tool_thinking_done" in kinds
    assert "tool_call_start" in kinds
    assert "tool_call_done" in kinds

    # tool_call_start 的 tool_name + args_summary 字段存在
    tc_start = next(e for e in emitted if e.get("kind") == "tool_call_start")
    assert tc_start["tool_name"] == "generate_position_report"
    assert "title=" in tc_start["tool_args_summary"]

    # tool_call_done 的 result_summary + elapsed_ms 存在
    tc_done = next(e for e in emitted if e.get("kind") == "tool_call_done")
    assert "job_interpretation" in tc_done["tool_result_summary"]
    assert tc_done["tool_elapsed_ms"] >= 0

    # iteration 字段都在
    for e in emitted:
        assert "iteration" in e


@pytest.mark.asyncio
async def test_research_agent_emits_tool_error_on_failure():
    """工具调用抛错时 tool_call_done 应带 tool_error 字段。"""
    from app.agents.prepare.research_agent import research_agent_node

    failing = MagicMock()
    failing.name = "extract_jd_text"
    failing.ainvoke = AsyncMock(side_effect=RuntimeError("upstream 500"))
    # generate_position_report 也提供，便于兜底
    fake_report = {"job_interpretation": {}, "resume_match": {}, "company_profile": {}, "interview_qa": [], "salary_range": {}, "prep_suggestions": []}
    report_tool = MagicMock(); report_tool.name = "generate_position_report"; report_tool.ainvoke = AsyncMock(return_value=fake_report)

    msg = AIMessage(content="", tool_calls=[{
        "name": "extract_jd_text",
        "args": {"text": "..."},
        "id": "c1",
    }])
    stop_msg = AIMessage(content="")

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)

    async def empty_stream(messages):
        return
        yield  # never

    mock_model.astream = empty_stream
    mock_model.ainvoke = AsyncMock(side_effect=[msg, stop_msg])

    emitted: list[dict] = []

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[failing, report_tool]),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
        patch("app.agents.prepare.research_agent.get_stream_writer", return_value=emitted.append),
    ):
        await research_agent_node(state)

    tc_done = next((e for e in emitted if e.get("kind") == "tool_call_done"), None)
    assert tc_done is not None
    assert tc_done.get("tool_error", "").startswith("upstream 500")


@pytest.mark.asyncio
async def test_research_agent_writer_none_does_not_raise():
    """get_stream_writer 返回 None（兼容场景）时节点不应崩。"""
    from app.agents.prepare.research_agent import research_agent_node

    fake_report = {"job_interpretation": {}, "resume_match": {}, "company_profile": {}, "interview_qa": [], "salary_range": {}, "prep_suggestions": []}
    report_tool = MagicMock(); report_tool.name = "generate_position_report"; report_tool.ainvoke = AsyncMock(return_value=fake_report)

    msg = AIMessage(content="", tool_calls=[{
        "name": "generate_position_report",
        "args": {"title": "x", "company": "y", "jd_summary": "", "requirements": [], "search_results": {}, "directions": ["x"]},
        "id": "c1",
    }])
    stop_msg = AIMessage(content="")

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)

    async def empty_stream(messages):
        return
        yield

    mock_model.astream = empty_stream
    mock_model.ainvoke = AsyncMock(side_effect=[msg, stop_msg])

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[report_tool]),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
        patch("app.agents.prepare.research_agent.get_stream_writer", return_value=None),
    ):
        result = await research_agent_node(state)

    assert result["job_intel"] is not None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/unit/test_research_agent_emit.py -k "emits_full or emits_tool_error or writer_none" -v
```

预期：3 条 FAIL

- [ ] **Step 3: 改 research_agent_node**

打开 `backend/app/agents/prepare/research_agent.py`，做如下改造：

A. 文件顶部 import 区加：

```python
from contextlib import suppress

try:
    from langgraph.config import get_stream_writer  # type: ignore
except ImportError:  # 老版本 LangGraph 兼容
    def get_stream_writer():  # type: ignore
        return None
```

B. 在 `research_agent_node` 开头拿 writer 与一个安全包装：

```python
async def research_agent_node(state: PrepareState) -> PrepareState:
    completed = state.get("completed_tools", [])

    if not state.get("jd_raw") and not state.get("jd_url"):
        log.info("research_agent_skip_no_jd")
        return {**state, "job_intel": None, "completed_tools": completed + ["research_agent"]}

    started = time.time()

    writer = get_stream_writer()

    def _emit(payload: dict) -> None:
        """安全 emit：writer 为 None 或抛错时静默跳过，绝不阻断业务。"""
        if writer is None:
            return
        try:
            writer(payload)
        except Exception as exc:
            log.warning("research_agent_emit_failed", error=str(exc))
```

C. 把原有的 ReAct loop 替换为带 emit 的版本（保留原有兜底逻辑）：

```python
    tools = await get_mcp_tools()
    if not tools:
        log.warning("research_agent_no_mcp_tools_fallback")
        return {**state, "job_intel": None, "completed_tools": completed + ["research_agent"]}

    tools_by_name = {t.name: t for t in tools}

    model = _chat_model().bind_tools(tools)
    messages: list = [
        SystemMessage(content=RESEARCH_AGENT_SYSTEM_PROMPT.format(context=_build_context(state))),
        HumanMessage(content="请开始调研。"),
    ]

    tools_used: list[str] = []
    final_thought = ""
    partial: dict[str, Any] = {}
    iteration = 0

    try:
        for iteration in range(MAX_ITERATIONS):
            elapsed = time.time() - started
            if elapsed > TOTAL_TIMEOUT_SECONDS:
                log.warning("research_agent_total_timeout", elapsed=elapsed)
                break

            think_step_id = f"think-{iteration}"
            _emit({"kind": "tool_thinking_start", "iteration": iteration, "step_id": think_step_id})

            # 流式调用 LLM，每个 chunk emit token 事件并累积成完整 response
            chunks = []
            async for chunk in model.astream(messages):
                chunks.append(chunk)
                token = chunk.content if isinstance(chunk.content, str) else ""
                if token:
                    _emit({
                        "kind": "tool_thinking_token",
                        "iteration": iteration,
                        "step_id": think_step_id,
                        "text": token,
                    })

            if chunks:
                response = chunks[0]
                for c in chunks[1:]:
                    response = response + c
            else:
                response = await asyncio.wait_for(model.ainvoke(messages), timeout=30)

            messages.append(response)
            _emit({"kind": "tool_thinking_done", "iteration": iteration, "step_id": think_step_id})

            if isinstance(response.content, str) and response.content.strip():
                final_thought = response.content.strip()[:300]

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                log.info("research_agent_llm_decided_to_stop", iteration=iteration)
                break

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {}) or {}
                call_id = tc.get("id", name)
                step_id = f"tool-{iteration}-{call_id}"

                _emit({
                    "kind": "tool_call_start",
                    "iteration": iteration,
                    "step_id": step_id,
                    "tool_name": name,
                    "tool_args_summary": _summarize_args(args),
                })

                t0 = time.time()
                tool = tools_by_name.get(name)
                if tool is None:
                    content = json.dumps({"error": f"unknown tool: {name}"})
                    _emit({
                        "kind": "tool_call_done",
                        "iteration": iteration,
                        "step_id": step_id,
                        "tool_error": f"unknown tool: {name}",
                        "tool_elapsed_ms": 0,
                    })
                else:
                    try:
                        result = await asyncio.wait_for(tool.ainvoke(args), timeout=30)
                        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                        tools_used.append(name)
                        if name == "extract_jd_text" and isinstance(result, dict):
                            partial.update({
                                "title": result.get("title", ""),
                                "company": result.get("company", ""),
                                "jd_summary": result.get("jd_summary", ""),
                                "requirements": result.get("requirements", []),
                            })
                        elif name == "web_search":
                            partial.setdefault("search_results", {}).setdefault("general", []).extend(result if isinstance(result, list) else [])
                        elif name == "extract_resume" and isinstance(result, dict):
                            partial["resume_content"] = result.get("summary", "")

                        _emit({
                            "kind": "tool_call_done",
                            "iteration": iteration,
                            "step_id": step_id,
                            "tool_result_summary": _summarize_result(result),
                            "tool_elapsed_ms": int((time.time() - t0) * 1000),
                        })
                    except Exception as exc:
                        log.warning("research_agent_tool_failed", tool=name, error=str(exc))
                        content = json.dumps({"error": str(exc)})
                        _emit({
                            "kind": "tool_call_done",
                            "iteration": iteration,
                            "step_id": step_id,
                            "tool_error": str(exc),
                            "tool_elapsed_ms": int((time.time() - t0) * 1000),
                        })

                messages.append(ToolMessage(content=content, tool_call_id=call_id, name=name))
    except asyncio.TimeoutError:
        log.warning("research_agent_iter_timeout")

    job_intel = _extract_final_report(messages)
    if job_intel is None:
        log.info("research_agent_no_final_report_force_finalize")
        job_intel = await _force_finalize(tools_by_name, partial)

    elapsed_ms = int((time.time() - started) * 1000)

    if job_intel is None:
        log.warning("research_agent_failed_no_report", elapsed_ms=elapsed_ms, tools_used=tools_used)
        return {**state, "job_intel": None, "completed_tools": completed + ["research_agent"]}

    job_intel["_trace"] = {
        "tools_used": tools_used,
        "iterations": iteration + 1,
        "elapsed_ms": elapsed_ms,
        "final_thought": final_thought,
    }

    log.info(
        "research_agent_done",
        tools_used=tools_used,
        iterations=iteration + 1,
        elapsed_ms=elapsed_ms,
    )
    return {**state, "job_intel": job_intel, "completed_tools": completed + ["research_agent"]}
```

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/unit/test_research_agent_emit.py -v
uv run pytest tests/unit/test_research_agent.py -v
```

预期：emit 测试 3 条 PASS，原 research_agent 测试不破坏。

- [ ] **Step 5: commit**

```bash
git add backend/app/agents/prepare/research_agent.py backend/tests/unit/test_research_agent_emit.py
git commit -m "feat(research_agent): ReAct loop 各步通过 astream_writer emit 工具级 SSE 事件"
```

---

### Task 3: `stream_prepare_events` 处理 `on_custom` 事件并转发为 SSE

**Files:**

- Modify: `backend/app/agents/prepare/graph.py`
- Create: `backend/tests/unit/test_prepare_stream_custom_events.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_prepare_stream_custom_events.py`：

```python
"""验证 stream_prepare_events 能把 on_custom 事件转换为前端约定的 SSE event。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_stream_forwards_tool_thinking_token_as_sse_event():
    """on_custom + kind=tool_thinking_token 应被转换为 event=tool_thinking_token 的 SSE 输出。"""
    from app.agents.prepare.graph import stream_prepare_events

    async def fake_astream_events(state, version="v2"):
        # 模拟 LangGraph 抛出 on_custom 事件
        yield {
            "event": "on_custom",
            "metadata": {"langgraph_node": "research_agent"},
            "data": {
                "kind": "tool_thinking_token",
                "iteration": 0,
                "step_id": "think-0",
                "text": "我先调研",
            },
        }
        # 然后图结束
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {"output": {"need_direction": False, "prepared_questions": [], "jd_context": None, "summary": "", "direction": "x"}},
        }

    mock_graph = MagicMock()
    mock_graph.astream_events = fake_astream_events

    events = []
    with patch("app.agents.prepare.graph.get_prepare_graph", return_value=mock_graph):
        async for ev in stream_prepare_events({"session_id": "s1"}):
            events.append(ev)

    matched = [e for e in events if e.get("event") == "tool_thinking_token"]
    assert len(matched) == 1
    assert matched[0]["data"]["text"] == "我先调研"
    assert matched[0]["data"]["iteration"] == 0
    assert matched[0]["data"]["node"] == "research_agent"


@pytest.mark.asyncio
async def test_stream_forwards_all_five_tool_event_kinds():
    """5 类工具级事件都能正确透传 SSE event 名。"""
    from app.agents.prepare.graph import stream_prepare_events

    kinds = [
        "tool_thinking_start", "tool_thinking_token", "tool_thinking_done",
        "tool_call_start", "tool_call_done",
    ]

    async def fake_astream_events(state, version="v2"):
        for k in kinds:
            yield {
                "event": "on_custom",
                "metadata": {"langgraph_node": "research_agent"},
                "data": {"kind": k, "iteration": 0, "step_id": "x"},
            }
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {"output": {"need_direction": False, "prepared_questions": [], "jd_context": None, "summary": "", "direction": ""}},
        }

    mock_graph = MagicMock()
    mock_graph.astream_events = fake_astream_events

    seen = set()
    with patch("app.agents.prepare.graph.get_prepare_graph", return_value=mock_graph):
        async for ev in stream_prepare_events({"session_id": "s1"}):
            if ev["event"] in kinds:
                seen.add(ev["event"])

    assert seen == set(kinds)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/unit/test_prepare_stream_custom_events.py -v
```

预期：2 条 FAIL（事件没被转发）

- [ ] **Step 3: 改 stream_prepare_events**

打开 `backend/app/agents/prepare/graph.py`，找到 `stream_prepare_events` 函数。在 `async for event in get_prepare_graph().astream_events(...)` 循环里，**插入** `on_custom` 分支（放在 `if ev_name == "on_chain_start"` 之前）：

```python
        ev_name = event.get("event", "")
        ev_node = event.get("metadata", {}).get("langgraph_node", "")

        # 工具级 SSE 事件：透传 research_agent ReAct loop 内部的自定义事件
        if ev_name == "on_custom":
            payload = event.get("data") or {}
            kind = payload.get("kind", "")
            if kind in {
                "tool_thinking_start",
                "tool_thinking_token",
                "tool_thinking_done",
                "tool_call_start",
                "tool_call_done",
            }:
                forwarded = {k: v for k, v in payload.items() if k != "kind"}
                forwarded.setdefault("node", ev_node or "research_agent")
                yield {"event": kind, "data": forwarded}
                continue

        # 现有 node_start / node_token / node_done 分支保持不变...
```

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/unit/test_prepare_stream_custom_events.py -v
uv run pytest tests/integration/test_prepare_with_mcp.py -v 2>&1 | tail -20
```

预期：新测试 2 条 PASS，原有集成测试不破坏。

- [ ] **Step 5: commit**

```bash
git add backend/app/agents/prepare/graph.py backend/tests/unit/test_prepare_stream_custom_events.py
git commit -m "feat(prepare): stream_prepare_events 转发 on_custom 工具级事件为前端 SSE"
```

---

## Phase 2 — 前端类型与 SSE 解析

### Task 4: 扩展前端类型定义

**Files:**

- Modify: `frontend/lib/prepare-types.ts`

- [ ] **Step 1: 看现有类型**

```bash
cd frontend
grep -n "PrepareSSEEvent\|TraceNodeData" lib/prepare-types.ts
```

- [ ] **Step 2: 扩展 PrepareSSEEvent 与新增类型**

打开 `frontend/lib/prepare-types.ts`，做如下三处改动：

A. 在文件末尾追加新类型：

```typescript
export interface ToolCallStep {
  stepId: string;
  toolName: string;
  argsSummary: string;
  resultSummary?: string;
  elapsedMs?: number;
  error?: string;
  status: "running" | "done" | "error";
}

export interface ReactIteration {
  index: number;
  thinkContent: string;
  thinkStatus: "running" | "done";
  toolCalls: ToolCallStep[];
}
```

B. 在 `PrepareSSEEvent.event` 联合里追加 5 个事件名（原有联合保留）：

```typescript
export interface PrepareSSEEvent {
  event:
    | "node_start"
    | "node_token"
    | "node_done"
    | "done"
    | "error"
    | "phase_change"
    | "turn_node_start"
    | "turn_node_token"
    | "turn_node_done"
    | "turn_delta"
    | "turn_state"
    | "turn_report"
    | "turn_done"
    // ★ 工具级 trace（仅 research_agent 节点）
    | "tool_thinking_start"
    | "tool_thinking_token"
    | "tool_thinking_done"
    | "tool_call_start"
    | "tool_call_done";
  data: {
    // ... 保留所有现有字段 ...
    // ★ 工具级 trace 新增字段
    iteration?: number;
    step_id?: string;
    tool_name?: string;
    tool_args_summary?: string;
    tool_result_summary?: string;
    tool_elapsed_ms?: number;
    tool_error?: string;
  };
}
```

C. 在 `TraceNodeData` 末尾追加两个字段：

```typescript
export interface TraceNodeData {
  // ... 保留所有现有字段 ...
  /** research_agent 节点专属：工具思考步骤树 */
  reactSteps?: ReactIteration[];
  /** research_agent 节点专属：ReAct loop 整体状态 */
  reactStatus?: "running" | "done";
}
```

- [ ] **Step 3: 跑 typecheck**

```bash
pnpm typecheck
```

预期：通过（types 是纯类型扩展不破坏现有）

- [ ] **Step 4: commit**

```bash
git add frontend/lib/prepare-types.ts
git commit -m "feat(types): SSE 事件协议追加 5 类工具级 trace 事件与对应类型"
```

---

### Task 5: SSE handler 按 step_id 聚合工具级事件

**Files:**

- Modify: `frontend/app/interview/_components/interview-chat.tsx`（或 trace 状态聚合所在文件）

- [ ] **Step 1: 定位现有 SSE handler**

```bash
grep -n "node_start\|node_done\|node_token" app/interview/_components/interview-chat.tsx | head -20
```

确认现有事件分发结构（通常在 onmessage / reducer 里有 switch 或 if-else 链）。

- [ ] **Step 2: 写最小测试**

按现有测试模式（参考 `interview-chat.test.tsx`），在 `interview-chat.test.tsx` 追加：

```typescript
import { describe, it, expect } from "vitest";
import { aggregateReactSteps } from "./interview-chat"; // 假设导出新工具函数

describe("aggregateReactSteps", () => {
  it("creates a new iteration when tool_thinking_start arrives", () => {
    const steps = aggregateReactSteps([], {
      event: "tool_thinking_start",
      data: { iteration: 0, step_id: "think-0" },
    });
    expect(steps).toHaveLength(1);
    expect(steps[0]).toMatchObject({
      index: 0,
      thinkStatus: "running",
      toolCalls: [],
    });
  });

  it("appends streamed think tokens to thinkContent", () => {
    let steps = aggregateReactSteps([], {
      event: "tool_thinking_start",
      data: { iteration: 0, step_id: "think-0" },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_thinking_token",
      data: { iteration: 0, step_id: "think-0", text: "我先" },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_thinking_token",
      data: { iteration: 0, step_id: "think-0", text: "调研" },
    });
    expect(steps[0].thinkContent).toBe("我先调研");
  });

  it("adds a running tool_call_start card and updates on tool_call_done", () => {
    let steps = aggregateReactSteps([], {
      event: "tool_thinking_start",
      data: { iteration: 0, step_id: "think-0" },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_call_start",
      data: {
        iteration: 0,
        step_id: "tool-0-c1",
        tool_name: "extract_jd_text",
        tool_args_summary: 'text="..."',
      },
    });
    expect(steps[0].toolCalls).toHaveLength(1);
    expect(steps[0].toolCalls[0].status).toBe("running");

    steps = aggregateReactSteps(steps, {
      event: "tool_call_done",
      data: {
        iteration: 0,
        step_id: "tool-0-c1",
        tool_result_summary: "{title, company}",
        tool_elapsed_ms: 1200,
      },
    });
    expect(steps[0].toolCalls[0].status).toBe("done");
    expect(steps[0].toolCalls[0].elapsedMs).toBe(1200);
    expect(steps[0].toolCalls[0].resultSummary).toBe("{title, company}");
  });

  it("marks tool call as error when tool_error is present", () => {
    let steps = aggregateReactSteps([], {
      event: "tool_thinking_start",
      data: { iteration: 0, step_id: "think-0" },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_call_start",
      data: {
        iteration: 0,
        step_id: "tool-0-c1",
        tool_name: "web_search",
        tool_args_summary: "",
      },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_call_done",
      data: {
        iteration: 0,
        step_id: "tool-0-c1",
        tool_error: "Tavily timeout",
        tool_elapsed_ms: 30000,
      },
    });
    expect(steps[0].toolCalls[0].status).toBe("error");
    expect(steps[0].toolCalls[0].error).toBe("Tavily timeout");
  });
});
```

- [ ] **Step 3: 跑测试确认失败**

```bash
pnpm test interview-chat -- --run
```

预期：4 条新 case FAIL（`aggregateReactSteps` 未导出）

- [ ] **Step 4: 实现 aggregateReactSteps 并 export**

在 `interview-chat.tsx` 文件顶层（或新建 `lib/react-steps-aggregator.ts` 并 re-export），加：

```typescript
import type { PrepareSSEEvent, ReactIteration } from "@/lib/prepare-types";

export function aggregateReactSteps(
  prev: ReactIteration[],
  event: PrepareSSEEvent,
): ReactIteration[] {
  const { data } = event;
  const iter = data.iteration ?? 0;
  const next = [...prev];

  // 确保 iteration slot 存在
  while (next.length <= iter) {
    next.push({
      index: next.length,
      thinkContent: "",
      thinkStatus: "running",
      toolCalls: [],
    });
  }

  const slot = { ...next[iter], toolCalls: [...next[iter].toolCalls] };

  switch (event.event) {
    case "tool_thinking_start":
      slot.thinkStatus = "running";
      break;
    case "tool_thinking_token":
      slot.thinkContent = slot.thinkContent + (data.text ?? "");
      break;
    case "tool_thinking_done":
      slot.thinkStatus = "done";
      break;
    case "tool_call_start": {
      slot.toolCalls.push({
        stepId: data.step_id ?? `tool-${iter}-${slot.toolCalls.length}`,
        toolName: data.tool_name ?? "unknown",
        argsSummary: data.tool_args_summary ?? "",
        status: "running",
      });
      break;
    }
    case "tool_call_done": {
      const idx = slot.toolCalls.findIndex((t) => t.stepId === data.step_id);
      if (idx >= 0) {
        const isError = !!data.tool_error;
        slot.toolCalls[idx] = {
          ...slot.toolCalls[idx],
          resultSummary: data.tool_result_summary,
          elapsedMs: data.tool_elapsed_ms,
          error: data.tool_error,
          status: isError ? "error" : "done",
        };
      }
      break;
    }
    default:
      return prev;
  }

  next[iter] = slot;
  return next;
}
```

- [ ] **Step 5: 在 interview-chat.tsx 的 SSE 主 handler 里调用**

在节点状态 reducer（更新 `TraceNodeData` 那段）里加分支：

```typescript
// 找到 research_agent 节点的 TraceNodeData，更新它的 reactSteps
if (
  event.event.startsWith("tool_thinking") ||
  event.event.startsWith("tool_call")
) {
  setTraceNodes((prev) =>
    prev.map((n) => {
      if (n.id !== "research_agent") return n;
      const newSteps = aggregateReactSteps(n.reactSteps ?? [], event);
      return { ...n, reactSteps: newSteps, reactStatus: "running" };
    }),
  );
  return;
}

// node_done for research_agent: mark reactStatus done
if (event.event === "node_done" && event.data.node === "research_agent") {
  setTraceNodes((prev) =>
    prev.map((n) =>
      n.id === "research_agent" ? { ...n, reactStatus: "done" } : n,
    ),
  );
  // 注意：node_done 原有逻辑（设置 status = done / elapsed 等）继续执行，这里只是补充 reactStatus
}
```

具体合并方式按 interview-chat.tsx 实际的 reducer 结构调整。

- [ ] **Step 6: 跑测试**

```bash
pnpm test interview-chat -- --run
pnpm typecheck
```

预期：单测全 PASS，typecheck 通过。

- [ ] **Step 7: commit**

```bash
git add frontend/app/interview/_components/interview-chat.tsx frontend/app/interview/_components/interview-chat.test.tsx
git commit -m "feat(trace): aggregateReactSteps 聚合工具级 SSE 事件到 ReactIteration[]"
```

---

## Phase 3 — 前端 UI 组件

### Task 6: ToolCallCard 组件

**Files:**

- Create: `frontend/app/interview/_components/tool-call-card.tsx`
- Create: `frontend/app/interview/_components/tool-call-card.test.tsx`

- [ ] **Step 1: 写失败测试**

创建 `frontend/app/interview/_components/tool-call-card.test.tsx`：

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ToolCallCard } from "./tool-call-card";
import type { ToolCallStep } from "@/lib/prepare-types";

const baseStep: ToolCallStep = {
  stepId: "tool-0-c1",
  toolName: "extract_jd_text",
  argsSummary: 'text="字节后端 JD..."',
  status: "running",
};

describe("ToolCallCard", () => {
  it("renders tool name and args summary", () => {
    render(<ToolCallCard step={baseStep} />);
    expect(screen.getByText("extract_jd_text")).toBeInTheDocument();
    expect(screen.getByText(/text="字节后端 JD/)).toBeInTheDocument();
  });

  it("shows running state with pulse animation indicator", () => {
    render(<ToolCallCard step={baseStep} />);
    const indicator = screen.getByTestId("tool-call-status-running");
    expect(indicator).toBeInTheDocument();
  });

  it("shows result summary and elapsed when done", () => {
    render(
      <ToolCallCard
        step={{
          ...baseStep,
          status: "done",
          resultSummary: "{title, company, requirements}",
          elapsedMs: 1200,
        }}
      />,
    );
    expect(screen.getByText(/title, company/)).toBeInTheDocument();
    expect(screen.getByText("1200ms")).toBeInTheDocument();
  });

  it("shows error message and red styling when error", () => {
    render(
      <ToolCallCard
        step={{
          ...baseStep,
          status: "error",
          error: "Tavily timeout",
          elapsedMs: 30000,
        }}
      />,
    );
    expect(screen.getByText(/Tavily timeout/)).toBeInTheDocument();
    expect(screen.getByTestId("tool-call-status-error")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pnpm test tool-call-card -- --run
```

预期：4 条 FAIL（组件不存在）

- [ ] **Step 3: 实现 ToolCallCard**

创建 `frontend/app/interview/_components/tool-call-card.tsx`：

```typescript
"use client";

import type { ToolCallStep } from "@/lib/prepare-types";

interface ToolCallCardProps {
  step: ToolCallStep;
}

export function ToolCallCard({ step }: ToolCallCardProps) {
  const statusClass =
    step.status === "error"
      ? "border-red-300/70 bg-red-50/60 dark:border-red-500/40 dark:bg-red-500/10"
      : step.status === "done"
        ? "border-emerald-300/60 bg-emerald-50/40 dark:border-emerald-500/30 dark:bg-emerald-500/10"
        : "border-[#534AB7]/30 bg-[#534AB7]/[0.04] dark:border-[#CECBF6]/30 dark:bg-[#CECBF6]/[0.05]";

  const Indicator = () => {
    if (step.status === "running") {
      return (
        <span
          data-testid="tool-call-status-running"
          className="inline-block h-2 w-2 rounded-full bg-[#534AB7] animate-pulse dark:bg-[#CECBF6]"
        />
      );
    }
    if (step.status === "error") {
      return (
        <span
          data-testid="tool-call-status-error"
          className="inline-block h-2 w-2 rounded-full bg-red-500"
        />
      );
    }
    return (
      <span
        data-testid="tool-call-status-done"
        className="inline-block h-2 w-2 rounded-full bg-emerald-500"
      />
    );
  };

  return (
    <div
      data-testid={`tool-call-card-${step.stepId}`}
      className={`mt-2 rounded-lg border px-3 py-2 text-xs transition-colors ${statusClass}`}
    >
      <div className="flex items-center gap-2">
        <Indicator />
        <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
          🔧 {step.toolName}
        </span>
        <span className="font-mono text-slate-500 dark:text-slate-400 truncate">
          ({step.argsSummary})
        </span>
        {step.elapsedMs !== undefined && (
          <span className="ml-auto tabular-nums text-[11px] text-slate-500 dark:text-slate-400">
            {step.elapsedMs}ms
          </span>
        )}
      </div>
      {step.status === "done" && step.resultSummary && (
        <div className="mt-1 pl-4 font-mono text-slate-600 dark:text-slate-300">
          ↳ {step.resultSummary}
        </div>
      )}
      {step.status === "error" && step.error && (
        <div className="mt-1 pl-4 text-red-700 dark:text-red-300">
          ↳ {step.error}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 跑测试**

```bash
pnpm test tool-call-card -- --run
```

预期：4 条 PASS

- [ ] **Step 5: commit**

```bash
git add frontend/app/interview/_components/tool-call-card.tsx frontend/app/interview/_components/tool-call-card.test.tsx
git commit -m "feat(trace): ToolCallCard 组件 — 工具调用卡片含状态切换与错误样式"
```

---

### Task 7: ReactStepTree + IterationGroup 组件

**Files:**

- Create: `frontend/app/interview/_components/react-step-tree.tsx`
- Create: `frontend/app/interview/_components/react-step-tree.test.tsx`

- [ ] **Step 1: 写失败测试**

创建 `frontend/app/interview/_components/react-step-tree.test.tsx`：

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReactStepTree } from "./react-step-tree";
import type { ReactIteration } from "@/lib/prepare-types";

describe("ReactStepTree", () => {
  it("renders nothing for empty steps", () => {
    const { container } = render(<ReactStepTree steps={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders one IterationGroup per iteration", () => {
    const steps: ReactIteration[] = [
      { index: 0, thinkContent: "Think A", thinkStatus: "done", toolCalls: [] },
      { index: 1, thinkContent: "Think B", thinkStatus: "running", toolCalls: [] },
    ];
    render(<ReactStepTree steps={steps} />);
    expect(screen.getByText("Think A")).toBeInTheDocument();
    expect(screen.getByText("Think B")).toBeInTheDocument();
    expect(screen.getAllByTestId(/iteration-group-/)).toHaveLength(2);
  });

  it("renders tool call cards inside iteration", () => {
    const steps: ReactIteration[] = [
      {
        index: 0,
        thinkContent: "Think A",
        thinkStatus: "done",
        toolCalls: [
          { stepId: "t-0-1", toolName: "extract_jd_text", argsSummary: "x", status: "done", resultSummary: "{a}", elapsedMs: 100 },
          { stepId: "t-0-2", toolName: "web_search", argsSummary: "y", status: "done", resultSummary: "[5 条]", elapsedMs: 200 },
        ],
      },
    ];
    render(<ReactStepTree steps={steps} />);
    expect(screen.getByText("extract_jd_text")).toBeInTheDocument();
    expect(screen.getByText("web_search")).toBeInTheDocument();
  });

  it("shows running pulse on think when thinkStatus is running", () => {
    const steps: ReactIteration[] = [
      { index: 0, thinkContent: "", thinkStatus: "running", toolCalls: [] },
    ];
    render(<ReactStepTree steps={steps} />);
    expect(screen.getByTestId("think-status-running-0")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pnpm test react-step-tree -- --run
```

预期：4 条 FAIL

- [ ] **Step 3: 实现组件**

创建 `frontend/app/interview/_components/react-step-tree.tsx`：

```typescript
"use client";

import type { ReactIteration } from "@/lib/prepare-types";
import { ToolCallCard } from "./tool-call-card";

interface ReactStepTreeProps {
  steps: ReactIteration[];
}

export function ReactStepTree({ steps }: ReactStepTreeProps) {
  if (!steps || steps.length === 0) return null;
  return (
    <div className="mt-2 space-y-3">
      {steps.map(step => (
        <IterationGroup key={step.index} step={step} />
      ))}
    </div>
  );
}

interface IterationGroupProps {
  step: ReactIteration;
}

function IterationGroup({ step }: IterationGroupProps) {
  return (
    <div
      data-testid={`iteration-group-${step.index}`}
      className="rounded-xl border border-[#534AB7]/15 bg-slate-50/50 px-3 py-2.5 dark:border-white/5 dark:bg-zinc-900/40"
    >
      <div className="mb-1 flex items-center gap-2 text-[10px] font-extrabold uppercase tracking-wide text-[#534AB7] dark:text-[#CECBF6]">
        第 {step.index + 1} 轮
      </div>
      <div className="flex items-start gap-2">
        <span className="text-sm leading-none">💭</span>
        <div className="flex-1 text-xs leading-relaxed text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
          {step.thinkContent || (
            <span className="text-slate-400 italic">（思考中…）</span>
          )}
          {step.thinkStatus === "running" && (
            <span
              data-testid={`think-status-running-${step.index}`}
              className="ml-1 inline-block h-2 w-2 rounded-full bg-[#534AB7] animate-pulse dark:bg-[#CECBF6]"
            />
          )}
        </div>
      </div>
      {step.toolCalls.map(tc => (
        <ToolCallCard key={tc.stepId} step={tc} />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: 跑测试**

```bash
pnpm test react-step-tree -- --run
```

预期：4 条 PASS

- [ ] **Step 5: commit**

```bash
git add frontend/app/interview/_components/react-step-tree.tsx frontend/app/interview/_components/react-step-tree.test.tsx
git commit -m "feat(trace): ReactStepTree + IterationGroup — 按轮次渲染 think + tool 调用"
```

---

### Task 8: TraceNode 集成 reactSteps + 折叠/展开

**Files:**

- Modify: `frontend/app/interview/_components/trace-node.tsx`
- Modify: `frontend/app/interview/_components/trace-node.test.tsx`

- [ ] **Step 1: 写失败测试**

在 `frontend/app/interview/_components/trace-node.test.tsx` 追加：

```typescript
import { fireEvent } from "@testing-library/react";

describe("TraceNode with reactSteps (research_agent only)", () => {
  const baseProps = {
    id: "research_agent",
    label: "岗位调研",
    title: "通过 MCP 调研目标岗位",
    status: "running" as const,
    tokens: "",
  };

  it("renders ReactStepTree when reactSteps are present", () => {
    render(
      <TraceNode
        {...baseProps}
        reactSteps={[
          { index: 0, thinkContent: "Think A", thinkStatus: "done", toolCalls: [] },
        ]}
      />,
    );
    expect(screen.getByText("Think A")).toBeInTheDocument();
  });

  it("expands by default when status is running", () => {
    render(
      <TraceNode
        {...baseProps}
        reactSteps={[
          { index: 0, thinkContent: "Think A", thinkStatus: "running", toolCalls: [] },
        ]}
      />,
    );
    expect(screen.getByTestId("iteration-group-0")).toBeVisible();
  });

  it("collapses by default when status is done", () => {
    render(
      <TraceNode
        {...baseProps}
        status="done"
        reactSteps={[
          { index: 0, thinkContent: "Think A", thinkStatus: "done", toolCalls: [] },
        ]}
      />,
    );
    expect(screen.queryByTestId("iteration-group-0")).not.toBeInTheDocument();
  });

  it("toggles open/closed when expand button is clicked", () => {
    render(
      <TraceNode
        {...baseProps}
        status="done"
        reactSteps={[
          { index: 0, thinkContent: "Think A", thinkStatus: "done", toolCalls: [] },
        ]}
      />,
    );
    const btn = screen.getByRole("button", { name: /展开|收起/ });
    fireEvent.click(btn);
    expect(screen.getByText("Think A")).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.queryByText("Think A")).not.toBeInTheDocument();
  });

  it("does not render expand button when id is not research_agent", () => {
    render(
      <TraceNode
        {...baseProps}
        id="memory_search"
        reactSteps={[
          { index: 0, thinkContent: "Think A", thinkStatus: "done", toolCalls: [] },
        ]}
      />,
    );
    expect(screen.queryByRole("button", { name: /展开|收起/ })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pnpm test trace-node -- --run
```

预期：5 条新 case FAIL

- [ ] **Step 3: 改 TraceNode**

打开 `frontend/app/interview/_components/trace-node.tsx`，做如下改动：

A. 顶部加 import：

```typescript
import { useState } from "react";
import type { ReactIteration } from "@/lib/prepare-types";
import { ReactStepTree } from "./react-step-tree";
```

B. props 接口加字段：

```typescript
interface TraceNodeProps {
  // ... 现有字段保持 ...
  reactSteps?: ReactIteration[];
}
```

C. 函数体里加状态 + 渲染：

```typescript
export function TraceNode({
  id, label, title, status, tokens, elapsedMs, isLast = false,
  candidateLevel, latentSignals, missingDimensions,
  chiefToolCalls, designedQuestion, designedCategory, summaryScore,
  reactSteps,
}: TraceNodeProps) {
  const isResearchAgent = id === "research_agent";
  const hasReactSteps = isResearchAgent && Array.isArray(reactSteps) && reactSteps.length > 0;

  const [userToggled, setUserToggled] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const effectiveOpen = userToggled ? isOpen : status === "running";

  // ... 现有 badgeClass、连接线、status icon 渲染保持 ...

  return (
    <div data-testid={`trace-node-${id}`} className="group flex gap-3 py-2.5">
      {/* 现有左侧 timeline 区保持 */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* 现有 header（label + title + elapsedMs）保持 */}
        {/* 现有 tokens / latentSignals / 等内容保持 */}

        {hasReactSteps && (
          <div className="mt-1">
            <button
              type="button"
              onClick={() => {
                setUserToggled(true);
                setIsOpen(!effectiveOpen);
              }}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#534AB7] hover:underline dark:text-[#CECBF6]"
            >
              {effectiveOpen ? "▾ 收起思考链" : "▸ 展开思考链"}
              <span className="text-slate-400">（{reactSteps!.length} 轮）</span>
            </button>
            {effectiveOpen && <ReactStepTree steps={reactSteps!} />}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 跑测试**

```bash
pnpm test trace-node -- --run
pnpm typecheck
```

预期：所有 trace-node 测试 PASS（含原有 + 新增 5 条），typecheck 通过。

- [ ] **Step 5: commit**

```bash
git add frontend/app/interview/_components/trace-node.tsx frontend/app/interview/_components/trace-node.test.tsx
git commit -m "feat(trace): TraceNode 集成 ReactStepTree 与展开/折叠（仅 research_agent）"
```

---

## Phase 4 — 端到端联调与发布

### Task 9: 端到端联调验证

**Files:** 无代码改动，纯手动验证。

- [ ] **Step 1: 启 job-intel MCP server（终端 A）**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent/backend
uv run python -m app.mcp_server
```

- [ ] **Step 2: 启 multi dev 全栈（终端 B）**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach
./dev.sh
```

- [ ] **Step 3: 浏览器开 multi 前端，启动一次备课（带 JD 文本）**

进 "开始模拟面试" → 填方向 + 公司 + 岗位 + JD → 启动备课。

- [ ] **Step 4: 观察 trace panel**

预期：

- `research_agent` 节点出现，状态 running
- **默认就是展开状态**，第 1 轮 think 文字流式吐出（一个字一个字蹦）
- think 结束后立即出现 `extract_jd_text` 工具卡片（状态 running 带 pulse）
- 卡片完成后立即变 done，显示结果摘要 + 耗时
- 进入第 2 轮：新的 IterationGroup 出现
- 节点完成时 `research_agent` 整体收起，"展开思考链" 按钮可见
- 点击按钮能再次展开看历史

- [ ] **Step 5: 测试错误路径**

人工拉一个工具失败：临时改 job-intel 的 web_search 让它抛错（或断网 Tavily 模拟），再跑一次备课。

预期：web_search 卡片显示红色边框 + 错误文字，但 research_agent 节点仍能正常完成（兜底走 generate_position_report）。

- [ ] **Step 6: 测试旧后端 / 新前端兼容**

关掉 job-intel MCP，再跑一次备课。

预期：research_agent 节点失败 → Supervisor 走 jd_analysis 兜底 → 题目正常出现；trace panel 里 research_agent 不显示思考链按钮（因为没收到工具事件）。

- [ ] **Step 7: 无需 commit**

仅手动验证。若发现 bug 回到对应 Task 修复。

---

### Task 10: 全量回归 + 推送 + PR

- [ ] **Step 1: 全部测试**

```bash
cd backend
uv run pytest tests/ -v 2>&1 | tail -20

cd ../frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

预期：单测全 PASS、typecheck 通过、build 成功。

- [ ] **Step 2: lint**

```bash
cd backend && uv run ruff check app/agents/prepare/research_agent.py app/agents/prepare/graph.py
```

预期：无错。

- [ ] **Step 3: 推送**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach
git push -u origin feature/react-tool-trace-viz
```

- [ ] **Step 4: 开 PR**

```bash
gh pr create --title "feat: research_agent 工具级 ReAct trace 可视化" --body "$(cat <<'EOF'
## Summary

- 后端：research_agent ReAct loop 通过 LangGraph `astream_writer` emit 5 类工具级 SSE 事件（tool_thinking_start/token/done + tool_call_start/done）
- 前端：扩展 SSE 协议、加 `aggregateReactSteps` 聚合到 `ReactIteration[]`、新增 `ReactStepTree` + `ToolCallCard` 组件
- TraceNode 在 research_agent 节点上加展开/折叠按钮：运行中默认展开、完成后默认收起
- 全程降级路径完备：writer/事件/工具任意失败都不阻断业务流

## 前置依赖

需要 `feature/research-agent-mcp` 已合入 main。

## Spec

`docs/superpowers/specs/2026-06-03-react-tool-trace-visualization-design.md`

## Plan

`docs/superpowers/plans/2026-06-03-react-tool-trace-visualization.md`

## Test plan

- [ ] 后端单元测试 PASS（含 emit 顺序、错误路径、writer=None 兼容）
- [ ] 前端单元测试 PASS（aggregateReactSteps + ToolCallCard + ReactStepTree + TraceNode）
- [ ] 浏览器联调：备课启动后 think 流式可见、tool 卡片实时出现、完成后可折叠
- [ ] 工具失败时卡片显示红色 + 错误信息
- [ ] 后端 MCP 不可用时前端仍能完成备课（思考链按钮不出现）

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

至此实施完成。

---

## 不在本期范围

| Follow-up                    | 范围                                                        |
| ---------------------------- | ----------------------------------------------------------- |
| Interviewer Chief 工具级展示 | 把 ReactStepTree 复用到面试阶段 chief.ainvoke 的 tool calls |
| 折叠状态持久化               | localStorage 记住"用户上次展开过的节点"                     |
| Trace 历史回放               | 面试详情页里能查看历史 research_agent 步骤树                |

---

## Self-Review 检查结果

- **Spec 覆盖**：第 3 章架构 → Tasks 2-3 / 4-8；第 4 章后端 emit → Tasks 1-3；第 5 章前端 → Tasks 4-8；第 6 章验收 → Task 9；第 7 章文件清单 → 已在本 plan File Structure 段对应
- **Placeholder 扫描**：无 TBD / TODO；每个 step 含具体代码或具体命令
- **类型一致性**：`ReactIteration` / `ToolCallStep` / `aggregateReactSteps` 在 Tasks 4-8 跨多 task 复用，签名一致；`tool_call_done` 既携带 `tool_result_summary` 也携带 `tool_error`（互斥）— Task 5 测试和 Task 6 组件都按这个约定写
