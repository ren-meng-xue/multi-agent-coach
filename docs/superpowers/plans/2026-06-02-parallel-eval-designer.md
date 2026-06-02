# Evaluator + Designer 并行执行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将候选人每次回答后的 Evaluator + Designer 串行等待改为 asyncio.gather 并行执行，总延迟从 `Evaluator + Designer` 降至 `max(Evaluator, Designer)`。

**Architecture:** Chief 发现本轮既无评估结果又无出题双方案时，用 `asyncio.gather` 同时启动 Evaluator 和 Designer；Designer 并行模式下生成追问 + 新题两个方案；Chief 拿到两个结果后根据评分和追问上限选一道题交给 `chief_respond`。

**Tech Stack:** Python asyncio, LangGraph StateGraph, LangChain ChatOpenAI with_structured_output, Pydantic BaseModel, pytest-asyncio

---

## 改动文件一览

| 文件                                        | 改动类型 | 职责                                                                                                           |
| ------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------- |
| `app/agents/interviewer/state.py`           | 修改     | 新增 `designer_dual_output` 字段                                                                               |
| `app/agents/designer/state.py`              | 修改     | 新增 `dual_output` 字段                                                                                        |
| `app/agents/designer/prompts.py`            | 修改     | 新增 `DESIGNER_DUAL_SYSTEM_PROMPT`                                                                             |
| `app/agents/designer/nodes.py`              | 修改     | 新增 `_DesignerDualOutput` 模型 + `design_dual` 节点                                                           |
| `app/agents/designer/graph.py`              | 修改     | 新增 `build_designer_dual_graph` + `run_designer_dual`                                                         |
| `app/agents/interviewer/chief.py`           | 修改     | 新增 `_pick_question` + `_execute_design_dual`；修改 `chief_think`、`chief_execute`、`route_after_chief_think` |
| `app/agents/interviewer/nodes.py`           | 修改     | `load_context_node` 重置 `designer_dual_output`                                                                |
| `tests/unit/test_parallel_eval_designer.py` | 新建     | 覆盖选题逻辑、design_dual、chief 并行分支                                                                      |

---

### Task 1: 新增 State 字段

**Files:**

- Modify: `backend/app/agents/interviewer/state.py`
- Modify: `backend/app/agents/designer/state.py`
- Test: `backend/tests/unit/test_parallel_eval_designer.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/unit/test_parallel_eval_designer.py`：

```python
"""并行 Evaluator + Designer 功能测试。"""
from app.agents.interviewer.state import InterviewState
from app.agents.designer.state import DesignerState


def test_interview_state_has_designer_dual_output_field():
    state: InterviewState = {"designer_dual_output": None}
    assert state.get("designer_dual_output") is None


def test_designer_state_has_dual_output_field():
    state: DesignerState = {"dual_output": {}}
    assert state.get("dual_output") == {}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py -v
```

期望输出：`KeyError` 或 TypedDict 检查失败。

- [ ] **Step 3: 在 InterviewState 新增字段**

打开 `backend/app/agents/interviewer/state.py`，在 `designer_output` 那行下方添加：

```python
    designer_output: dict[str, Any] | None
    designer_dual_output: dict[str, Any] | None   # 并行模式下 Designer 的双方案原始输出
```

- [ ] **Step 4: 在 DesignerState 新增字段**

打开 `backend/app/agents/designer/state.py`，在 `output` 那行下方添加：

```python
    output: dict[str, Any]
    dual_output: dict[str, Any]   # 并行模式下的双方案输出 {followup_question, new_question, source}
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_interview_state_has_designer_dual_output_field tests/unit/test_parallel_eval_designer.py::test_designer_state_has_dual_output_field -v
```

期望输出：`2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/interviewer/state.py backend/app/agents/designer/state.py backend/tests/unit/test_parallel_eval_designer.py
git commit -m "feat: add designer_dual_output state fields for parallel eval+design"
```

---

### Task 2: Designer 双方案 Prompt + 模型 + 节点

**Files:**

- Modify: `backend/app/agents/designer/prompts.py`
- Modify: `backend/app/agents/designer/nodes.py`
- Test: `backend/tests/unit/test_parallel_eval_designer.py`

- [ ] **Step 1: 写失败测试**

在 `test_parallel_eval_designer.py` 追加：

```python
from unittest.mock import AsyncMock, patch
import pytest
from app.agents.designer.nodes import design_dual
from app.agents.designer.state import DesignerState


@pytest.mark.asyncio
async def test_design_dual_returns_both_questions():
    """design_dual 节点返回 dual_output，包含 followup_question 和 new_question。"""
    from app.agents.designer.nodes import _DesignerDualOutput
    fake_output = _DesignerDualOutput(
        followup_question="请量化一下提升了多少？",
        new_question="说一个你做过的系统设计决策。",
    )
    state: DesignerState = {
        "focus": "dual",
        "target_role": "后端工程师",
        "previous_questions": [],
    }
    with patch(
        "app.agents.designer.nodes._chat_model",
        return_value=AsyncMock(
            with_structured_output=lambda _: AsyncMock(ainvoke=AsyncMock(return_value=fake_output))
        ),
    ):
        result = await design_dual(state)

    dual = result.get("dual_output") or {}
    assert "followup_question" in dual
    assert "new_question" in dual
    assert len(dual["followup_question"]) > 0
    assert len(dual["new_question"]) > 0


@pytest.mark.asyncio
async def test_design_dual_fallback_on_llm_error():
    """LLM 调用失败时，design_dual 返回兜底文案而不是异常。"""
    state: DesignerState = {
        "focus": "dual",
        "target_role": "后端工程师",
        "previous_questions": [],
    }
    with patch(
        "app.agents.designer.nodes._chat_model",
        return_value=AsyncMock(
            with_structured_output=lambda _: AsyncMock(ainvoke=AsyncMock(side_effect=RuntimeError("LLM down")))
        ),
    ):
        result = await design_dual(state)

    dual = result.get("dual_output") or {}
    assert len(dual.get("followup_question", "")) > 0
    assert len(dual.get("new_question", "")) > 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_design_dual_returns_both_questions -v
```

期望：`ImportError: cannot import name 'design_dual'`

- [ ] **Step 3: 在 prompts.py 新增双方案 prompt**

打开 `backend/app/agents/designer/prompts.py`，在文件末尾追加：

```python
DESIGNER_DUAL_SYSTEM_PROMPT = (
    "你是 AI 面试委员会的出题专家。\n"
    "请根据以下上下文，同时设计两个问题：\n"
    "1. followup_question：追问（假设候选人本轮回答深度不足，需要继续挖掘）\n"
    "2. new_question：新题（假设候选人本轮回答充分，进入下一个考察方向）\n\n"
    "【要求】\n"
    "- 追问必须针对候选人回答中的具体缺口，禁止万金油（禁止"展开说说""为什么这么做"）\n"
    "- 新题不能与已问过的问题重复\n"
    "- 每个问题只问一件事，不要输出解释，不要赞美候选人\n\n"
    "【上下文】\n{context}"
)
```

- [ ] **Step 4: 在 nodes.py 新增 \_DesignerDualOutput 模型和 design_dual 节点**

打开 `backend/app/agents/designer/nodes.py`，在文件顶部 import 区增加：

```python
from app.agents.designer.prompts import DESIGNER_DUAL_SYSTEM_PROMPT, DESIGNER_SYSTEM_PROMPT
```

（替换原有的单行 `from app.agents.designer.prompts import DESIGNER_SYSTEM_PROMPT`）

在 `_DesignedQuestion` 类定义之后追加：

```python
class _DesignerDualOutput(BaseModel):
    followup_question: str = ""
    new_question: str = ""
```

在 `respond_to_chief` 函数之后追加：

```python
async def design_dual(state: DesignerState) -> DesignerState:
    """并行模式：一次 LLM 调用同时生成追问和新题两个方案。"""
    context = _build_context(state)
    followup_question = ""
    new_question = ""
    try:
        model = _chat_model().with_structured_output(_DesignerDualOutput)
        out = await model.ainvoke(
            [
                SystemMessage(content=DESIGNER_DUAL_SYSTEM_PROMPT.format(context=context)),
                *[m for m in state.get("messages", []) if isinstance(m, BaseMessage)][-8:],
            ]
        )
        if isinstance(out, _DesignerDualOutput):
            followup_question = out.followup_question.strip()
            new_question = out.new_question.strip()
    except Exception as exc:
        log.warning("designer_dual_llm_failed", error=str(exc))

    focus = state.get("focus") or "当前回答的薄弱点"
    role = state.get("target_role") or "该岗位"
    if not followup_question:
        followup_question = (
            f"围绕{focus}，请结合真实项目说明你的约束条件、方案选择和最终效果数据。"
        )
    if not new_question:
        new_question = (
            f"请分享一个在{role}工作中遇到的技术挑战，以及你是如何解决的？"
        )

    # 确保以问号结尾
    if "？" not in followup_question and "?" not in followup_question:
        followup_question = followup_question.rstrip("。") + "？"
    if "？" not in new_question and "?" not in new_question:
        new_question = new_question.rstrip("。") + "？"

    dual_output = {
        "followup_question": followup_question,
        "new_question": new_question,
        "source": "llm",
    }
    return cast(DesignerState, {**dict(state), "dual_output": dual_output})
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_design_dual_returns_both_questions tests/unit/test_parallel_eval_designer.py::test_design_dual_fallback_on_llm_error -v
```

期望：`2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/designer/prompts.py backend/app/agents/designer/nodes.py backend/tests/unit/test_parallel_eval_designer.py
git commit -m "feat: add DESIGNER_DUAL_SYSTEM_PROMPT and design_dual node for parallel mode"
```

---

### Task 3: Designer Graph 新增 run_designer_dual

**Files:**

- Modify: `backend/app/agents/designer/graph.py`
- Test: `backend/tests/unit/test_parallel_eval_designer.py`

- [ ] **Step 1: 写失败测试**

在 `test_parallel_eval_designer.py` 追加：

```python
from app.agents.designer.graph import run_designer_dual


@pytest.mark.asyncio
async def test_run_designer_dual_returns_dual_output():
    """run_designer_dual 返回包含 followup_question 和 new_question 的 dict。"""
    state = {
        "focus": "dual",
        "target_role": "后端工程师",
        "previous_questions": [],
    }
    dual_data = {
        "followup_question": "追问内容？",
        "new_question": "新题内容？",
        "source": "llm",
    }
    with patch(
        "app.agents.designer.nodes.design_dual",
        new=AsyncMock(return_value={**state, "dual_output": dual_data}),
    ):
        result = await run_designer_dual(state)

    assert result.get("followup_question") == "追问内容？"
    assert result.get("new_question") == "新题内容？"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_run_designer_dual_returns_dual_output -v
```

期望：`ImportError: cannot import name 'run_designer_dual'`

- [ ] **Step 3: 在 graph.py 新增 build_designer_dual_graph 和 run_designer_dual**

打开 `backend/app/agents/designer/graph.py`，在文件末尾追加：

```python
def build_designer_dual_graph():
    """并行模式专用图：只跑 design_dual 节点，不经过单方案 validate/respond。"""
    graph = StateGraph(DesignerState)
    graph.add_node("design_dual", nodes.design_dual)
    graph.set_entry_point("design_dual")
    graph.add_edge("design_dual", END)
    return graph.compile()


async def run_designer_dual(state: DesignerState) -> dict[str, Any]:
    """调用并行模式 Designer，返回 {followup_question, new_question, source}。"""
    out = await build_designer_dual_graph().ainvoke(state)
    return dict(out.get("dual_output") or {})
```

同时在文件顶部的 `__all__` 或 import 中导出 `run_designer_dual`（如果有 `__all__`，追加 `"run_designer_dual"`）。

- [ ] **Step 4: 在 designer/**init**.py 导出 run_designer_dual**

打开 `backend/app/agents/designer/__init__.py`，更新为：

```python
"""Question Designer Agent exports."""

from app.agents.designer.graph import build_designer_graph, run_designer, run_designer_dual

__all__ = ["build_designer_graph", "run_designer", "run_designer_dual"]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_run_designer_dual_returns_dual_output -v
```

期望：`1 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/designer/graph.py backend/app/agents/designer/__init__.py backend/tests/unit/test_parallel_eval_designer.py
git commit -m "feat: add run_designer_dual for parallel mode Designer graph"
```

---

### Task 4: Chief 辅助函数 + 路由更新

**Files:**

- Modify: `backend/app/agents/interviewer/chief.py`
- Test: `backend/tests/unit/test_parallel_eval_designer.py`

- [ ] **Step 1: 写失败测试**

在 `test_parallel_eval_designer.py` 追加：

```python
from app.agents.interviewer.chief import _pick_question


def test_pick_question_low_score_returns_followup():
    """分数低且追问未到上限：选追问。"""
    eval_report = {"scoring": {"summary_score": 5.0, "missing_dimensions": ["量化结果"]}}
    dual = {"followup_question": "追问？", "new_question": "新题？"}
    result = _pick_question(eval_report, dual, followup_count=0, max_followups=2)
    assert result == "追问？"


def test_pick_question_high_score_returns_new_question():
    """分数高且无缺失维度：选新题。"""
    eval_report = {"scoring": {"summary_score": 8.0, "missing_dimensions": []}}
    dual = {"followup_question": "追问？", "new_question": "新题？"}
    result = _pick_question(eval_report, dual, followup_count=0, max_followups=2)
    assert result == "新题？"


def test_pick_question_max_followups_forces_new_question():
    """追问次数达上限：强制选新题，不管分数。"""
    eval_report = {"scoring": {"summary_score": 4.0, "missing_dimensions": ["量化"]}}
    dual = {"followup_question": "追问？", "new_question": "新题？"}
    result = _pick_question(eval_report, dual, followup_count=2, max_followups=2)
    assert result == "新题？"


def test_pick_question_none_eval_report_returns_followup():
    """eval_report 为 None（Evaluator 失败）时：回退到追问（保守策略）。"""
    dual = {"followup_question": "追问？", "new_question": "新题？"}
    result = _pick_question(None, dual, followup_count=0, max_followups=2)
    assert result == "追问？"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_pick_question_low_score_returns_followup -v
```

期望：`ImportError: cannot import name '_pick_question'`

- [ ] **Step 3: 在 chief.py 顶部新增 asyncio import 和 run_designer_dual import**

打开 `backend/app/agents/interviewer/chief.py`，在文件顶部找到 import 区：

将：

```python
from app.agents.designer import run_designer
```

替换为：

```python
import asyncio

from app.agents.designer import run_designer, run_designer_dual
```

- [ ] **Step 4: 在 chief.py 新增 \_pick_question 和 \_execute_design_dual**

在 `_execute_design` 函数之后（`chief_execute` 函数之前）追加：

```python
def _pick_question(
    eval_report: dict[str, Any] | None,
    designer_dual: dict[str, Any],
    followup_count: int,
    max_followups: int,
) -> str:
    """根据评分和追问次数上限选择追问还是新题。"""
    answer_sufficient = _answer_is_sufficient(eval_report)
    if answer_sufficient or followup_count >= max_followups:
        return designer_dual.get("new_question", "")
    return designer_dual.get("followup_question", "")


async def _execute_design_dual(state: InterviewState) -> dict[str, Any]:
    """并行模式下调用 Designer，生成追问和新题双方案。"""
    return await run_designer_dual(
        {
            "focus": "dual",
            "target_role": state.get("target_role", ""),
            "target_company": state.get("target_company", ""),
            "user_background": state.get("user_background", ""),
            "candidate_profile": state.get("candidate_profile") or {},
            "jd_context": state.get("jd_context"),
            "previous_questions": _previous_questions(state),
            "prepared_questions": state.get("prepared_questions") or [],
            "current_question_index": state.get(
                "current_question_index", state.get("question_count", 0)
            ),
            "evaluator_report": None,
            "messages": state.get("messages", []),
        }
    )
```

- [ ] **Step 5: 更新 route_after_chief_think 加入新 action**

找到：

```python
def route_after_chief_think(state: InterviewState) -> str:
    action = state.get("chief_next_action", "respond")
    if action in {"evaluate_answer", "design_question", "query_profile"}:
        return "chief_execute"
    return "chief_respond"
```

替换为：

```python
def route_after_chief_think(state: InterviewState) -> str:
    action = state.get("chief_next_action", "respond")
    if action in {"evaluate_answer", "design_question", "query_profile", "evaluate_and_design"}:
        return "chief_execute"
    return "chief_respond"
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_pick_question_low_score_returns_followup tests/unit/test_parallel_eval_designer.py::test_pick_question_high_score_returns_new_question tests/unit/test_parallel_eval_designer.py::test_pick_question_max_followups_forces_new_question tests/unit/test_parallel_eval_designer.py::test_pick_question_none_eval_report_returns_followup -v
```

期望：`4 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/interviewer/chief.py backend/tests/unit/test_parallel_eval_designer.py
git commit -m "feat: add _pick_question, _execute_design_dual, route update for parallel action"
```

---

### Task 5: 修改 chief_think 加入并行逻辑

**Files:**

- Modify: `backend/app/agents/interviewer/chief.py`
- Test: `backend/tests/unit/test_parallel_eval_designer.py`

- [ ] **Step 1: 写失败测试**

在 `test_parallel_eval_designer.py` 追加：

```python
from app.agents.interviewer.chief import chief_think
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_chief_think_sets_evaluate_and_design_when_no_results():
    """中段轮次，无评估结果也无双方案：action 应为 evaluate_and_design。"""
    state = {
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "chief_iteration": 0,
        "messages": [HumanMessage(content="我做过 Redis 缓存优化")],
        "evaluator_report": None,
        "designer_dual_output": None,
        "designer_output": None,
    }
    with patch(
        "app.agents.interviewer.chief._chief_reason_stream", new=AsyncMock(return_value=None)
    ):
        result = await chief_think(state)

    assert result["chief_next_action"] == "evaluate_and_design"


@pytest.mark.asyncio
async def test_chief_think_picks_followup_when_parallel_results_ready_low_score():
    """并行结果就绪且分数低：chief_think 选追问，设置 designer_output，清除 designer_dual_output。"""
    dual = {"followup_question": "能量化一下吗？", "new_question": "说个系统设计？", "source": "llm"}
    eval_report = {"scoring": {"summary_score": 4.0, "missing_dimensions": ["量化"]}}
    state = {
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "chief_iteration": 1,
        "messages": [HumanMessage(content="我做了优化")],
        "evaluator_report": eval_report,
        "designer_dual_output": dual,
        "designer_output": None,
    }
    with patch(
        "app.agents.interviewer.chief._chief_reason_stream", new=AsyncMock(return_value=None)
    ):
        result = await chief_think(state)

    assert result["chief_next_action"] == "respond"
    assert result.get("designer_output", {}).get("question_text") == "能量化一下吗？"
    assert result.get("designer_dual_output") is None


@pytest.mark.asyncio
async def test_chief_think_picks_new_question_when_parallel_results_ready_high_score():
    """并行结果就绪且分数高：chief_think 选新题，设置 designer_output。"""
    dual = {"followup_question": "追问？", "new_question": "新题？", "source": "llm"}
    eval_report = {"scoring": {"summary_score": 8.5, "missing_dimensions": []}}
    state = {
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "chief_iteration": 1,
        "messages": [HumanMessage(content="我做了很好的优化，提升了 30%")],
        "evaluator_report": eval_report,
        "designer_dual_output": dual,
        "designer_output": None,
    }
    with patch(
        "app.agents.interviewer.chief._chief_reason_stream", new=AsyncMock(return_value=None)
    ):
        result = await chief_think(state)

    assert result["chief_next_action"] == "respond"
    assert result.get("designer_output", {}).get("question_text") == "新题？"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_chief_think_sets_evaluate_and_design_when_no_results -v
```

期望：`FAILED`（当前 chief_think 没有 evaluate_and_design 分支）

- [ ] **Step 3: 修改 chief_think**

找到 `chief_think` 函数内下面这段并删除（旧的串行分支）：

```python
    elif not state.get("evaluator_report"):
        action = "evaluate_answer"
        tool_input = {"latest_answer": latest_answer}
        thought = "先委托评估专家分析本轮回答。"
    elif not state.get("designer_output"):
        answer_sufficient = _answer_is_sufficient(state.get("evaluator_report"))
        if question_count >= total_questions and (answer_sufficient or followup_count >= max_followups):
            action = "respond"
            tool_input = {"response_kind": "closing"}
            thought = "题数已满，准备收尾。"
        else:
            action = "design_question"
            if not answer_sufficient and followup_count < max_followups:
                focus = _followup_focus(state.get("evaluator_report"))
                tool_input = {"focus": focus}
                thought = f"回答尚不充分，委托出题专家设计追问：{focus}。"
            else:
                tool_input = {"focus": "new_question"}
                thought = "回答可接受或追问达到上限，委托出题专家设计下一题。"
```

替换为：

```python
    elif not state.get("evaluator_report") and not state.get("designer_dual_output"):
        action = "evaluate_and_design"
        tool_input = {"latest_answer": latest_answer}
        thought = "并行委托：评估专家分析回答 + 出题专家提前准备双方案。"
    elif state.get("evaluator_report") and state.get("designer_dual_output"):
        eval_report = state.get("evaluator_report")
        dual = state.get("designer_dual_output") or {}
        answer_sufficient = _answer_is_sufficient(eval_report)
        if question_count >= total_questions and (answer_sufficient or followup_count >= max_followups):
            thoughts.append("题数已满，准备收尾。")
            return {
                **state,
                "chief_next_action": "respond",
                "chief_tool_input": {"response_kind": "closing"},
                "chief_thoughts": thoughts,
            }
        picked = _pick_question(eval_report, dual, followup_count, max_followups)
        is_followup = not answer_sufficient and followup_count < max_followups
        thoughts.append(f"并行结果就绪，选{'追问' if is_followup else '新题'}。")
        return {
            **state,
            "chief_next_action": "respond",
            "chief_tool_input": {},
            "chief_thoughts": thoughts,
            "designer_output": {"question_text": picked, "source": dual.get("source", "llm")},
            "designer_dual_output": None,
        }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_chief_think_sets_evaluate_and_design_when_no_results tests/unit/test_parallel_eval_designer.py::test_chief_think_picks_followup_when_parallel_results_ready_low_score tests/unit/test_parallel_eval_designer.py::test_chief_think_picks_new_question_when_parallel_results_ready_high_score -v
```

期望：`3 passed`

- [ ] **Step 5: 运行全量路由测试确认无回归**

```bash
cd backend && uv run pytest tests/unit/test_interviewer_chain_routing.py tests/unit/test_interviewer_master_node.py -v
```

期望：全部通过

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/interviewer/chief.py backend/tests/unit/test_parallel_eval_designer.py
git commit -m "feat: modify chief_think to use evaluate_and_design parallel action"
```

---

### Task 6: chief_execute 并行分支 + 状态重置

**Files:**

- Modify: `backend/app/agents/interviewer/chief.py`
- Modify: `backend/app/agents/interviewer/nodes.py`
- Test: `backend/tests/unit/test_parallel_eval_designer.py`

- [ ] **Step 1: 写失败测试**

在 `test_parallel_eval_designer.py` 追加：

```python
from app.agents.interviewer.chief import chief_execute


@pytest.mark.asyncio
async def test_chief_execute_parallel_calls_both_agents():
    """evaluate_and_design action：Evaluator 和 Designer 被同时调用（asyncio.gather）。"""
    eval_result = {"scoring": {"summary_score": 5.0, "missing_dimensions": []}, "updated_profile": {}}
    dual_result = {"followup_question": "追问？", "new_question": "新题？", "source": "llm"}

    state = {
        "chief_next_action": "evaluate_and_design",
        "chief_tool_input": {"latest_answer": "候选人的回答"},
        "chief_iteration": 0,
        "chief_tool_results": [],
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [HumanMessage(content="候选人的回答")],
        "evaluator_report": None,
        "designer_dual_output": None,
        "turn_evaluations": [],
    }

    eval_mock = AsyncMock(return_value=eval_result)
    design_mock = AsyncMock(return_value=dual_result)

    with patch("app.agents.interviewer.chief._execute_evaluate", new=eval_mock), \
         patch("app.agents.interviewer.chief._execute_design_dual", new=design_mock):
        result = await chief_execute(state)

    eval_mock.assert_awaited_once()
    design_mock.assert_awaited_once()
    assert result.get("evaluator_report") == eval_result
    assert result.get("designer_dual_output") == dual_result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_chief_execute_parallel_calls_both_agents -v
```

期望：`FAILED`（chief_execute 还没有 evaluate_and_design 分支）

- [ ] **Step 3: 在 chief_execute 新增 evaluate_and_design 并行分支**

找到 `chief_execute` 函数内的 `try` 块，在现有 `if action == "evaluate_answer":` 之前追加：

```python
        if action == "evaluate_and_design":
            eval_report, dual = await asyncio.gather(
                _execute_evaluate(state),
                _execute_design_dual(state),
            )
            scoring = eval_report.get("scoring") or {}
            updated_evals = list(state.get("turn_evaluations") or [])
            if scoring:
                updated_evals.append(cast(TurnEvaluation, scoring))
            partial = {
                "evaluator_report": eval_report,
                "designer_dual_output": dual,
                "candidate_profile": eval_report.get("updated_profile") or state.get("candidate_profile") or {},
                "turn_evaluations": updated_evals,
            }
            results.append({"tool": "evaluate_and_design", "result": {"eval": eval_report, "dual": dual}})
        elif action == "evaluate_answer":
```

（把原来的 `if action == "evaluate_answer":` 改为 `elif action == "evaluate_answer":`）

- [ ] **Step 4: 在 load_context_node 重置 designer_dual_output**

打开 `backend/app/agents/interviewer/nodes.py`，找到 `load_context_node` 函数的 return 语句，在现有字段后追加：

```python
        "evaluator_report": None,
        "designer_output": None,
        "designer_dual_output": None,   # 新增：每轮开始前清空双方案缓存
```

（如果 `evaluator_report` 和 `designer_output` 已在 return 里，只需追加 `"designer_dual_output": None`）

- [ ] **Step 5: 在 chief_respond 清除 designer_dual_output**

找到 `chief_respond` 函数里所有返回 dict 并包含 `"designer_output": None` 的地方，追加 `"designer_dual_output": None`：

```python
            return {
                "stage": "interview",
                "question_count": next_count,
                "followup_count": 0,
                "current_question_index": idx + idx_delta,
                "assistant_message": await _question_reply(state, designed),
                "evaluator_report": None,
                "designer_output": None,
                "designer_dual_output": None,   # 新增
            }
```

以及另一个分支：

```python
        return {
            "stage": "interview",
            "followup_count": state.get("followup_count", 0) + 1,
            "assistant_message": str(designed["question_text"]),
            "evaluator_report": None,
            "designer_output": None,
            "designer_dual_output": None,   # 新增
        }
```

- [ ] **Step 6: 运行并行分支测试**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py::test_chief_execute_parallel_calls_both_agents -v
```

期望：`1 passed`

- [ ] **Step 7: 运行全量测试**

```bash
cd backend && uv run pytest tests/unit/test_parallel_eval_designer.py tests/unit/test_interviewer_chain_routing.py tests/unit/test_interviewer_master_node.py tests/unit/test_interview_turn_trace.py -v
```

期望：全部通过

- [ ] **Step 8: Ruff + Mypy 检查**

```bash
cd backend && uv run ruff check app/agents/interviewer/chief.py app/agents/designer/ && uv run mypy app/agents/interviewer/chief.py app/agents/designer/
```

期望：无 error

- [ ] **Step 9: Commit**

```bash
git add backend/app/agents/interviewer/chief.py backend/app/agents/interviewer/nodes.py backend/tests/unit/test_parallel_eval_designer.py
git commit -m "feat: add parallel evaluate_and_design branch in chief_execute + state resets"
```

---

## 验收检查

运行全套测试：

```bash
cd backend && uv run pytest tests/unit/ -v --tb=short
```

手动验证（需要后端服务运行）：

1. 查看日志中 Evaluator 和 Designer 的调用时间戳有重叠（`evaluate_and_design` 动作下）
2. 回答质量差的轮次：面试官发出追问
3. 回答质量好的轮次：面试官发出新题
4. 追问 2 次后（`followup_count == max_followups`）：强制出新题
5. 首轮行为不变：只走单方案 Designer（action = `design_question`）
