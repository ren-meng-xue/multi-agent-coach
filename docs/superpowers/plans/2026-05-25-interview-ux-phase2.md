# 面试房间 UX 阶段 2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为面试房间添加开场白、结束过渡和结构化报告卡，消除空白状态和 closing 后静默重启 bug。

**Architecture:** 后端 LangGraph 图在 closing 节点后新增 report 节点（closing → report → END），通过 SSE `report` 事件下发结构化评分数据；前端预置静态开场消息，检测 closing 阶段显示"开始新一轮"按钮，内联渲染 ReportCard 组件。

**Tech Stack:** Python 3.12 / FastAPI / LangGraph / LangChain / Pydantic v2 / pytest-asyncio · Next.js 15 / React / TypeScript / shadcn/ui / Vitest / @testing-library/react

---

## 文件结构

| 文件 | 类型 | 职责 |
|------|------|------|
| `backend/app/agents/interviewer/state.py` | 修改 | 新增 `report` 字段 |
| `backend/app/agents/interviewer/prompts.py` | 修改 | 新增 `REPORT_SYSTEM_PROMPT` |
| `backend/app/agents/interviewer/nodes.py` | 修改 | 新增 `ReportOutput`、`generate_report_output`、`report_node` |
| `backend/app/agents/interviewer/graph.py` | 修改 | closing → report → END |
| `backend/app/services/interview_turn.py` | 修改 | closing 阶段补发 `report` SSE 事件 |
| `backend/tests/unit/test_interviewer_graph.py` | 修改 | 新增 report_node 单元测试 |
| `backend/tests/integration/test_interview_turn_service.py` | 修改 | 新增 report SSE 集成测试 |
| `frontend/lib/interview-chat.ts` | 修改 | 新增 `InterviewReport` 类型、`onReport` 回调 |
| `frontend/lib/interview-chat.test.ts` | 修改 | 新增 report 事件测试 |
| `frontend/app/interview/_components/report-card.tsx` | 新建 | 内联评分卡组件 |
| `frontend/app/interview/_components/report-card.test.tsx` | 新建 | ReportCard 测试 |
| `frontend/app/interview/_components/interview-chat.tsx` | 修改 | 开场消息 + closing 按钮 + 报告卡渲染 |
| `frontend/app/interview/_components/interview-chat.test.tsx` | 修改 | 更新 4 个场景 |

---

### Task 1: 后端基础 — state 字段 + REPORT_SYSTEM_PROMPT

**Files:**
- Modify: `backend/app/agents/interviewer/state.py`
- Modify: `backend/app/agents/interviewer/prompts.py`

纯增量修改，无逻辑，下游任务验证行为。

- [ ] **Step 1: 在 state.py 新增 report 字段**

将 `backend/app/agents/interviewer/state.py` 替换为：

```python
"""LangGraph state for the single interviewer agent."""
from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

InterviewStage = Literal["opening", "interview", "closing"]


class InterviewState(TypedDict, total=False):
    """Graph state shared-1 by interviewer nodes."""

    session_id: str
    user_id: str
    is_first_time: bool
    target_role: str
    target_company: str
    user_background: str
    messages: list[BaseMessage]
    stage: InterviewStage
    question_count: int
    total_questions: int
    followup_count: int
    max_followups: int
    assistant_message: str
    opening_complete: bool
    decision_action: str
    decision_reason: str
    followup_question: str
    report: dict[str, Any]
```

- [ ] **Step 2: 在 prompts.py 末尾追加 REPORT_SYSTEM_PROMPT**

在 `backend/app/agents/interviewer/prompts.py` 末尾追加：

```python
REPORT_SYSTEM_PROMPT = (
    "你是面试评估专家。请根据完整的面试对话对候选人进行结构化评分。"
    "评分维度各 0-5 分：technical_depth（技术深度）、quantified_results（量化结果）、"
    "failure_tradeoffs（失败与权衡）、structure（结构完整性）。"
    "overall_score = 各维度均值 × 2，保留一位小数。"
    "highlights：2-3 条具体亮点；improvements：2-3 条具体改进建议。"
    "所有文字字段必须用中文。"
)
```

- [ ] **Step 3: typecheck**

```bash
cd backend && .venv/bin/python -m mypy app/agents-1/interviewer/state.py app/agents-1/interviewer/prompts.py
```

Expected: `Success: no issues found in 2 source files`

- [ ] **Step 4: commit**

```bash
git add backend/app/agents-1/interviewer/state.py backend/app/agents-1/interviewer/prompts.py
git commit -m "feat(interview): 新增 InterviewState.report 字段与 REPORT_SYSTEM_PROMPT"
```

---

### Task 2: 后端 — report_node 实现 + 单元测试

**Files:**
- Modify: `backend/app/agents/interviewer/nodes.py`
- Modify: `backend/tests/unit/test_interviewer_graph.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_interviewer_graph.py` 末尾追加：

```python
async def test_report_node_returns_structured_report(monkeypatch):
    """report_node 在完整对话后返回含所有字段的结构化评分。"""
    from app.agents.interviewer.nodes import ReportOutput, report_node

    async def fake_generate_report(state):
        return ReportOutput(
            overall_score=7.5,
            technical_depth=4.0,
            quantified_results=3.0,
            failure_tradeoffs=4.0,
            structure=3.5,
            highlights=["设计清晰", "表达有条理"],
            improvements=["缺少量化数据", "可补充失败案例"],
        )

    monkeypatch.setattr("app.agents-1.interviewer.nodes.generate_report_output", fake_generate_report)

    state = {
        "session_id": "s1",
        "user_id": "u1",
        "is_first_time": False,
        "messages": [HumanMessage(content="用了缓存方案"), AIMessage(content="不错")],
        "stage": "closing",
        "question_count": 5,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }

    result = await report_node(state)

    assert result["report"]["overall_score"] == 7.5
    assert result["report"]["technical_depth"] == 4.0
    assert result["report"]["highlights"] == ["设计清晰", "表达有条理"]
    assert result["report"]["improvements"] == ["缺少量化数据", "可补充失败案例"]


async def test_report_node_returns_empty_dict_on_unexpected_output(monkeypatch):
    """generate_report_output 返回 None 时，report_node 返回空 dict 并记录 warning。"""
    from app.agents.interviewer.nodes import report_node

    async def fake_generate_report(state):
        return None

    monkeypatch.setattr("app.agents-1.interviewer.nodes.generate_report_output", fake_generate_report)

    state = {
        "session_id": "s2",
        "user_id": "u1",
        "is_first_time": False,
        "messages": [HumanMessage(content="回答")],
        "stage": "closing",
        "question_count": 5,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }

    result = await report_node(state)
    assert result["report"] == {}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_graph.py::test_report_node_returns_structured_report tests/unit/test_interviewer_graph.py::test_report_node_returns_empty_dict_on_unexpected_output -v
```

Expected: FAILED — `ImportError: cannot import name 'report_node'`

- [ ] **Step 3: 实现 nodes.py**

在 `backend/app/agents/interviewer/nodes.py` 中，将 imports 段的 `prompts` 导入改为（追加 `REPORT_SYSTEM_PROMPT`）：

```python
from app.agents.interviewer.prompts import (
    CLOSING_SYSTEM_PROMPT,
    DECIDE_SYSTEM_PROMPT,
    OPENING_INFO_SYSTEM_PROMPT,
    OPENING_SYSTEM_PROMPT,
    QUESTION_SYSTEM_PROMPT,
    REPORT_SYSTEM_PROMPT,
)
```

在文件末尾（`closing_node` 之后）追加：

```python
class ReportOutput(BaseModel):
    """Structured interview assessment report."""

    overall_score: float
    technical_depth: float
    quantified_results: float
    failure_tradeoffs: float
    structure: float
    highlights: list[str]
    improvements: list[str]


async def generate_report_output(state: InterviewState) -> ReportOutput | None:
    """Call LLM with structured output to generate interview assessment."""
    model = _chat_model().with_structured_output(ReportOutput)
    output = await model.ainvoke(
        [SystemMessage(content=REPORT_SYSTEM_PROMPT), *_state_messages(state)]
    )
    if isinstance(output, ReportOutput):
        return output
    return None


async def report_node(state: InterviewState) -> InterviewState:
    """面试结束后生成结构化评分报告。"""
    output = await generate_report_output(state)
    if output is None:
        log.warning("interviewer_report_unexpected_output")
        return {"report": {}}
    return {"report": output.model_dump()}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_graph.py::test_report_node_returns_structured_report tests/unit/test_interviewer_graph.py::test_report_node_returns_empty_dict_on_unexpected_output -v
```

Expected: 2 passed

- [ ] **Step 5: 全量单元测试**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/ -v
```

Expected: all pass

- [ ] **Step 6: commit**

```bash
git add backend/app/agents-1/interviewer/nodes.py backend/tests/unit/test_interviewer_graph.py
git commit -m "feat(interview): 新增 report_node 生成结构化面试评分，补 TDD 单元测试"
```

---

### Task 3: 后端 — graph.py 接线 report 节点

**Files:**
- Modify: `backend/app/agents/interviewer/graph.py`
- Modify: `backend/tests/unit/test_interviewer_graph.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_interviewer_graph.py` 末尾追加：

```python
async def test_closing_turn_returns_report_in_state(monkeypatch):
    """closing 阶段完成后，图输出 state 中包含 report 字段。"""
    from app.agents.interviewer.nodes import ReportOutput

    async def fake_closing(state):
        return "本次模拟面试结束，感谢参与。"

    async def fake_generate_report(state):
        return ReportOutput(
            overall_score=8.0,
            technical_depth=4.0,
            quantified_results=4.0,
            failure_tradeoffs=4.0,
            structure=4.0,
            highlights=["整体表现良好"],
            improvements=["可补充更多细节"],
        )

    monkeypatch.setattr("app.agents-1.interviewer.nodes.generate_closing_reply", fake_closing)
    monkeypatch.setattr("app.agents-1.interviewer.nodes.generate_report_output", fake_generate_report)

    out = await run_interviewer_turn(
        {
            "session_id": "session-report-1",
            "user_id": "user-1",
            "is_first_time": False,
            "messages": [HumanMessage(content="第五题回答内容详细。")],
            "stage": "interview",
            "question_count": 5,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "closing"
    assert out["assistant_message"] == "本次模拟面试结束，感谢参与。"
    assert "report" in out
    assert out["report"]["overall_score"] == 8.0
    assert out["report"]["highlights"] == ["整体表现良好"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_graph.py::test_closing_turn_returns_report_in_state -v
```

Expected: FAILED — `out` 中无 `report` 字段

- [ ] **Step 3: 修改 graph.py 的 build_interviewer_graph**

将 `backend/app/agents/interviewer/graph.py` 中 `build_interviewer_graph` 函数里的节点注册和边定义改为：

```python
def build_interviewer_graph(checkpointer: Any | None = None):
    """Build and compile the interviewer StateGraph."""
    graph = StateGraph(InterviewState)
    graph.add_node("load_context", nodes.load_context_node)
    graph.add_node("opening", nodes.opening_node)
    graph.add_node("ask_question", nodes.ask_question_node)
    graph.add_node("decide_next", nodes.decide_next_node)
    graph.add_node("followup", nodes.followup_node)
    graph.add_node("closing", nodes.closing_node)
    graph.add_node("report", nodes.report_node)

    graph.set_entry_point("load_context")
    graph.add_conditional_edges(
        "load_context",
        route_after_load,
        {
            "opening": "opening",
            "ask_question": "ask_question",
            "decide_next": "decide_next",
            "closing": "closing",
        },
    )
    graph.add_conditional_edges(
        "decide_next",
        route_after_decide,
        {
            "followup": "followup",
            "ask_question": "ask_question",
            "closing": "closing",
        },
    )
    graph.add_conditional_edges(
        "opening",
        lambda state: "ask_question" if state.get("opening_complete") else "end",
        {
            "ask_question": "ask_question",
            "end": END,
        },
    )
    graph.add_edge("ask_question", END)
    graph.add_edge("followup", END)
    graph.add_edge("closing", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_graph.py::test_closing_turn_returns_report_in_state -v
```

Expected: PASSED

- [ ] **Step 5: 全量单元测试**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/ -v
```

Expected: all pass

- [ ] **Step 6: commit**

```bash
git add backend/app/agents-1/interviewer/graph.py backend/tests/unit/test_interviewer_graph.py
git commit -m "feat(interview): graph 接线 report 节点，closing → report → END"
```

---

### Task 4: 后端 — interview_turn.py 补发 report 事件 + 集成测试

**Files:**
- Modify: `backend/app/services/interview_turn.py`
- Modify: `backend/tests/integration/test_interview_turn_service.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/integration/test_interview_turn_service.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_stream_interview_turn_emits_report_event_on_closing(db, monkeypatch):
    """closing 阶段完成后，stream_interview_turn 在 done 前发出 report 事件，含 overall_score 字段。"""

    async def fake_graph_events(state):
        yield {"event": "token", "data": {"text": "感谢参与本次模拟面试。"}}
        yield {
            "event": "final",
            "data": {
                **state,
                "stage": "closing",
                "question_count": 5,
                "followup_count": 0,
                "assistant_message": "感谢参与本次模拟面试。",
                "report": {
                    "overall_score": 7.5,
                    "technical_depth": 4.0,
                    "quantified_results": 3.0,
                    "failure_tradeoffs": 4.0,
                    "structure": 3.5,
                    "highlights": ["表达清晰"],
                    "improvements": ["可补充量化数据"],
                },
            },
        }

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events", fake_graph_events
    )
    user_id = f"user_turn_report_{uuid4().hex}"

    events = [
        event
        async for event in stream_interview_turn("第五题回答", user_id=user_id, db=db)
    ]

    event_names = [e["event"] for e in events]
    assert event_names == ["delta", "state", "report", "done"]

    report_event = next(e for e in events if e["event"] == "report")
    assert report_event["data"]["overall_score"] == 7.5
    assert report_event["data"]["highlights"] == ["表达清晰"]


@pytest.mark.asyncio
async def test_stream_interview_turn_skips_report_event_when_empty(db, monkeypatch):
    """report_node 返回空 dict 时，不发 report 事件，closing 消息正常显示。"""

    async def fake_graph_events(state):
        yield {"event": "token", "data": {"text": "感谢参与。"}}
        yield {
            "event": "final",
            "data": {
                **state,
                "stage": "closing",
                "question_count": 5,
                "followup_count": 0,
                "assistant_message": "感谢参与。",
                "report": {},
            },
        }

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events", fake_graph_events
    )
    user_id = f"user_turn_no_report_{uuid4().hex}"

    events = [
        event
        async for event in stream_interview_turn("第五题回答", user_id=user_id, db=db)
    ]

    event_names = [e["event"] for e in events]
    assert "report" not in event_names
    assert event_names == ["delta", "state", "done"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_interview_turn_service.py::test_stream_interview_turn_emits_report_event_on_closing tests/integration/test_interview_turn_service.py::test_stream_interview_turn_skips_report_event_when_empty -v
```

Expected: FAILED — report 事件未发出

- [ ] **Step 3: 修改 interview_turn.py**

在 `stream_interview_turn` 函数中，将末尾的 `db.add_all / commit / done` 段改为：

```python
    db.add_all(
        [
            InterviewMessage(
                session_id=session.id,
                role="user",
                content=message,
                question_number=session.question_count or None,
            ),
            InterviewMessage(
                session_id=session.id,
                role="assistant",
                content=assistant_content,
                question_number=session.question_count or None,
            ),
        ]
    )
    await db.commit()

    if session.stage == "closing":
        report_data = output.get("report")
        if report_data:
            yield {"event": "report", "data": report_data}

    yield {"event": "done", "data": {}}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_interview_turn_service.py::test_stream_interview_turn_emits_report_event_on_closing tests/integration/test_interview_turn_service.py::test_stream_interview_turn_skips_report_event_when_empty -v
```

Expected: 2 passed

- [ ] **Step 5: 全量后端测试 + lint + typecheck**

```bash
cd backend && .venv/bin/python -m pytest tests/ -v && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy app
```

Expected: all pass, no errors

- [ ] **Step 6: commit**

```bash
git add backend/app/services/interview_turn.py backend/tests/integration/test_interview_turn_service.py
git commit -m "feat(interview): closing 阶段补发 report SSE 事件，并补集成测试"
```

---

### Task 5: 前端 — interview-chat.ts 新增 InterviewReport 和 onReport

**Files:**
- Modify: `frontend/lib/interview-chat.ts`
- Modify: `frontend/lib/interview-chat.test.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/lib/interview-chat.test.ts` 的 `describe` 块末尾追加：

```typescript
  it("收到 report 事件时调用 onReport 回调", async () => {
    const reportPayload = {
      overall_score: 7.5,
      technical_depth: 4.0,
      quantified_results: 3.0,
      failure_tradeoffs: 4.0,
      structure: 3.5,
      highlights: ["表达清晰"],
      improvements: ["可补充量化数据"],
    };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          makeSseStream(
            `event: state\ndata: {"stage":"closing","question_count":5,"total_questions":5}\n\n` +
              `event: report\ndata: ${JSON.stringify(reportPayload)}\n\n` +
              `event: done\ndata: {}\n\n`,
          ),
          { status: 200 },
        ),
      ),
    );

    const reports: unknown[] = [];
    await streamInterviewChat({
      token: "test-token",
      message: "第五题",
      onDelta: vi.fn(),
      onReport: (report) => reports.push(report),
    });

    expect(reports).toHaveLength(1);
    expect(reports[0]).toMatchObject({ overall_score: 7.5, highlights: ["表达清晰"] });
  });
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd frontend && pnpm test lib/interview-chat.test.ts
```

Expected: FAILED — `onReport` 不存在，`report` 事件未处理

- [ ] **Step 3: 修改 interview-chat.ts**

将 `frontend/lib/interview-chat.ts` 替换为：

```typescript
import { readSseStream, type SseEvent } from "./sse";

export type InterviewChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type InterviewProgressState = {
  stage: "opening" | "interview" | "closing";
  question_count: number;
  total_questions: number;
};

export interface InterviewReport {
  overall_score: number;
  technical_depth: number;
  quantified_results: number;
  failure_tradeoffs: number;
  structure: number;
  highlights: string[];
  improvements: string[];
}

type StreamInterviewChatOptions = {
  token: string;
  message: string;
  signal?: AbortSignal;
  onDelta: (text: string) => void;
  onState?: (state: InterviewProgressState) => void;
  onReport?: (report: InterviewReport) => void;
};

const DEFAULT_ERROR_MESSAGE = "请求失败，请稍后重试";

/** 调用后端统一面试入口，并把 SSE state / delta / report 事件交给 UI 层渲染。 */
export async function streamInterviewChat({
  token,
  message,
  signal,
  onDelta,
  onState,
  onReport,
}: StreamInterviewChatOptions): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) {
    throw new Error("缺少后端接口配置");
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/turn`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }

  await readSseStream({
    stream: response.body,
    onEvent: (event) => handleSseEvent(event, onDelta, onState, onReport),
  });
}

function handleSseEvent(
  { event, data }: SseEvent,
  onDelta: (text: string) => void,
  onState?: (state: InterviewProgressState) => void,
  onReport?: (report: InterviewReport) => void,
) {
  if (event === "done") return;

  if (event === "state") {
    const payload = parseJsonPayload<InterviewProgressState>(data);
    onState?.(payload);
    return;
  }

  if (event === "delta") {
    const payload = parseJsonPayload<{ text?: string }>(data);
    if (payload.text) onDelta(payload.text);
    return;
  }

  if (event === "report") {
    const payload = parseJsonPayload<InterviewReport>(data);
    onReport?.(payload);
    return;
  }

  if (event === "error") {
    const payload = parseJsonPayload<{ message?: string }>(data);
    throw new Error(payload.message || DEFAULT_ERROR_MESSAGE);
  }
}

function parseJsonPayload<T>(data: string): T {
  try {
    return JSON.parse(data) as T;
  } catch {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd frontend && pnpm test lib/interview-chat.test.ts
```

Expected: all pass

- [ ] **Step 5: typecheck**

```bash
cd frontend && pnpm typecheck
```

Expected: no errors

- [ ] **Step 6: commit**

```bash
git add frontend/lib/interview-chat.ts frontend/lib/interview-chat.test.ts
git commit -m "feat(interview): 新增 InterviewReport 类型和 onReport 回调"
```

---

### Task 6: 前端 — ReportCard 组件

**Files:**
- Create: `frontend/app/interview/_components/report-card.tsx`
- Create: `frontend/app/interview/_components/report-card.test.tsx`

- [ ] **Step 1: 写失败测试**

新建 `frontend/app/interview/_components/report-card.test.tsx`：

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReportCard } from "./report-card";
import type { InterviewReport } from "@/lib/interview-chat";

const sampleReport: InterviewReport = {
  overall_score: 7.5,
  technical_depth: 4.0,
  quantified_results: 3.0,
  failure_tradeoffs: 4.0,
  structure: 3.5,
  highlights: ["设计清晰", "表达有条理"],
  improvements: ["缺少量化数据", "可补充失败案例"],
};

describe("ReportCard", () => {
  it("渲染综合评分和四个维度分数", () => {
    render(<ReportCard report={sampleReport} />);

    expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
    expect(screen.getByText("7.5 / 10")).toBeInTheDocument();
    expect(screen.getByText("4.0 / 5")).toBeInTheDocument();
    expect(screen.getByText("3.5 / 5")).toBeInTheDocument();
  });

  it("渲染亮点和改进建议列表", () => {
    render(<ReportCard report={sampleReport} />);

    expect(screen.getByText("设计清晰")).toBeInTheDocument();
    expect(screen.getByText("表达有条理")).toBeInTheDocument();
    expect(screen.getByText("缺少量化数据")).toBeInTheDocument();
    expect(screen.getByText("可补充失败案例")).toBeInTheDocument();
  });

  it("highlights 和 improvements 为空数组时不崩溃", () => {
    render(<ReportCard report={{ ...sampleReport, highlights: [], improvements: [] }} />);
    expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd frontend && pnpm test app/interview/_components/report-card.test.tsx
```

Expected: FAILED — `report-card.tsx` 不存在

- [ ] **Step 3: 新建 report-card.tsx**

新建 `frontend/app/interview/_components/report-card.tsx`：

```tsx
import type { InterviewReport } from "@/lib/interview-chat";

const DIMENSION_LABELS: Record<
  "technical_depth" | "quantified_results" | "failure_tradeoffs" | "structure",
  string
> = {
  technical_depth: "技术深度",
  quantified_results: "量化结果",
  failure_tradeoffs: "失败与权衡",
  structure: "结构完整性",
};

const DIMENSIONS = Object.keys(DIMENSION_LABELS) as Array<keyof typeof DIMENSION_LABELS>;

function ScoreBar({ score }: { score: number }) {
  const percent = Math.round((Math.min(Math.max(score, 0), 5) / 5) * 100);
  return (
    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
      <div
        className="h-full rounded-full bg-[#534AB7] transition-[width] duration-500"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

export function ReportCard({ report }: { report: InterviewReport }) {
  return (
    <div className="mx-auto w-full max-w-xl rounded-xl border border-black/10 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1c1c1a]">
      <h2 className="mb-1 text-sm font-bold text-black/80 dark:text-white/80">本轮面试报告</h2>
      <div className="mb-4 flex items-baseline gap-1.5">
        <span className="bg-gradient-to-br from-[#534AB7] to-rose-600 bg-clip-text text-3xl font-bold text-transparent">
          {report.overall_score.toFixed(1)}
        </span>
        <span className="text-sm text-black/45 dark:text-white/45">/ 10</span>
      </div>

      <div className="mb-4 space-y-2.5">
        {DIMENSIONS.map((key) => (
          <div key={key} className="flex items-center gap-3">
            <span className="w-20 shrink-0 text-xs text-black/55 dark:text-white/55">
              {DIMENSION_LABELS[key]}
            </span>
            <ScoreBar score={report[key]} />
            <span className="w-12 shrink-0 text-right text-xs font-medium text-black/70 dark:text-white/70">
              {report[key].toFixed(1)} / 5
            </span>
          </div>
        ))}
      </div>

      {report.highlights.length > 0 && (
        <div className="mb-3">
          <p className="mb-1.5 text-xs font-semibold text-black/60 dark:text-white/60">亮点</p>
          <ul className="space-y-1">
            {report.highlights.map((item, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-black/70 dark:text-white/70">
                <span className="mt-0.5 shrink-0 text-[#534AB7]">·</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.improvements.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold text-black/60 dark:text-white/60">改进建议</p>
          <ul className="space-y-1">
            {report.improvements.map((item, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-black/70 dark:text-white/70">
                <span className="mt-0.5 shrink-0 text-rose-500">·</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd frontend && pnpm test app/interview/_components/report-card.test.tsx
```

Expected: 3 passed

- [ ] **Step 5: commit**

```bash
git add frontend/app/interview/_components/report-card.tsx frontend/app/interview/_components/report-card.test.tsx
git commit -m "feat(interview): 新增 ReportCard 组件，内联展示结构化评分"
```

---

### Task 7: 前端 — InterviewChat 主组件改造

**Files:**
- Modify: `frontend/app/interview/_components/interview-chat.tsx`
- Modify: `frontend/app/interview/_components/interview-chat.test.tsx`

**注意：** 引入 `OPENING_MESSAGE` 后，`messages` 初始值不再为 `[]`，导致现有测试
"无会话内容时，复制会话按钮处于禁用状态" 失效（按钮将始终启用）。Step 1 同时更新该测试。

- [ ] **Step 1: 写/更新测试**

在 `frontend/app/interview/_components/interview-chat.test.tsx` 中：

**1a. 将现有测试（第 131-135 行）从：**
```typescript
  it("无会话内容时，复制会话按钮处于禁用状态", () => {
    render(<InterviewChat />);
    const copyButton = screen.getByRole("button", { name: /复制会话/i });
    expect(copyButton).toBeDisabled();
  });
```
**改为：**
```typescript
  it("初始渲染时复制按钮已启用（有开场引导消息）", () => {
    render(<InterviewChat />);
    const copyButton = screen.getByRole("button", { name: /复制会话/i });
    expect(copyButton).not.toBeDisabled();
  });
```

**1b. 在 describe 块末尾追加以下 4 个新测试：**
```tsx
  it("初始渲染时显示 AI 开场引导消息，不为空白", () => {
    render(<InterviewChat />);
    expect(screen.getByText(/目标岗位/)).toBeInTheDocument();
  });

  it("closing 阶段显示「开始新一轮面试」按钮，输入框仍可使用", async () => {
    mockStreamInterviewChat.mockImplementation(async ({ onState }) => {
      onState?.({ stage: "closing", question_count: 5, total_questions: 5 });
    });

    render(<InterviewChat />);

    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "最后一题");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "开始新一轮面试" })).toBeInTheDocument();
    });
    expect(screen.getByLabelText("输入面试练习内容")).not.toBeDisabled();
  });

  it("点击「开始新一轮面试」后，消息重置为开场消息，报告消失", async () => {
    mockStreamInterviewChat.mockImplementation(async ({ onState, onReport }) => {
      onState?.({ stage: "closing", question_count: 5, total_questions: 5 });
      onReport?.({
        overall_score: 7.5,
        technical_depth: 4.0,
        quantified_results: 3.0,
        failure_tradeoffs: 4.0,
        structure: 3.5,
        highlights: ["表达清晰"],
        improvements: ["可补充量化数据"],
      });
    });

    render(<InterviewChat />);

    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "最后一题");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "开始新一轮面试" }));

    await waitFor(() => {
      expect(screen.queryByText("本轮面试报告")).not.toBeInTheDocument();
    });
    expect(screen.getByText(/目标岗位/)).toBeInTheDocument();
  });

  it("收到 report 事件后，ReportCard 在聊天流末尾渲染", async () => {
    mockStreamInterviewChat.mockImplementation(async ({ onState, onReport, onDelta }) => {
      onState?.({ stage: "closing", question_count: 5, total_questions: 5 });
      onDelta("感谢参与本次面试。");
      onReport?.({
        overall_score: 8.0,
        technical_depth: 4.0,
        quantified_results: 4.0,
        failure_tradeoffs: 4.0,
        structure: 4.0,
        highlights: ["整体良好"],
        improvements: ["补充细节"],
      });
    });

    render(<InterviewChat />);

    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "第五题");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
    });
    expect(screen.getByText("8.0 / 10")).toBeInTheDocument();
    expect(screen.getByText("整体良好")).toBeInTheDocument();
  });
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd frontend && pnpm test app/interview/_components/interview-chat.test.tsx
```

Expected: 4 new tests FAILED，原有测试改动后通过

- [ ] **Step 3: 修改 interview-chat.tsx**

将 `frontend/app/interview/_components/interview-chat.tsx` 替换为：

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import {
  streamInterviewChat,
  type InterviewChatMessage,
  type InterviewProgressState,
  type InterviewReport,
} from "@/lib/interview-chat";
import { MessageBubble } from "./message-bubble";
import { ChatInput } from "./chat-input";
import { ReportCard } from "./report-card";
import { Button } from "@/components/ui/button";
import { Copy, Check } from "lucide-react";

const OPENING_MESSAGE: InterviewChatMessage = {
  role: "assistant",
  content:
    "你好！在开始之前，请告诉我：\n\n**① 目标岗位**（如 AI Agent 工程师）\n**② 目标公司类型**（大厂 / 创业公司 / 外企）\n**③ 想练习的项目背景**（一句话简述）",
};

const INITIAL_PROGRESS: InterviewProgressState = {
  stage: "opening",
  question_count: 0,
  total_questions: 5,
};

/** 面试房间的单面试官流式聊天主体。 */
export function InterviewChat() {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<InterviewChatMessage[]>([OPENING_MESSAGE]);
  const [progress, setProgress] = useState<InterviewProgressState>(INITIAL_PROGRESS);
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [copied, setCopied] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const assistantIndexRef = useRef<number | null>(null);
  const deltaBufferRef = useRef("");
  const frameRef = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages, report]);

  function flushBufferedDelta() {
    const text = deltaBufferRef.current;
    const assistantIndex = assistantIndexRef.current;
    if (!text || assistantIndex === null) return;

    deltaBufferRef.current = "";
    setMessages((current) =>
      current.map((message, index) =>
        index === assistantIndex
          ? { ...message, content: `${message.content}${text}` }
          : message,
      ),
    );
  }

  function scheduleDeltaFlush() {
    if (frameRef.current !== null) return;

    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = null;
      flushBufferedDelta();
    });
  }

  function discardBufferedDelta() {
    deltaBufferRef.current = "";
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
  }

  function handleNewRound() {
    abortRef.current?.abort();
    discardBufferedDelta();
    setMessages([OPENING_MESSAGE]);
    setProgress(INITIAL_PROGRESS);
    setReport(null);
  }

  async function handleCopyChat() {
    if (messages.length === 0) return;

    const chatText = messages
      .map((msg) => {
        const roleName = msg.role === "user" ? "求职者" : "面试官";
        return `【${roleName}】：${msg.content}`;
      })
      .join("\n\n");

    try {
      await navigator.clipboard.writeText(chatText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy chat: ", err);
    }
  }

  async function handleSend(content: string) {
    if (!content || isStreaming) return;

    abortRef.current?.abort();
    const abortController = new AbortController();
    abortRef.current = abortController;

    const userMessage: InterviewChatMessage = { role: "user", content };
    const assistantIndex = messages.length + 1;
    const nextMessages = [...messages, userMessage, { role: "assistant" as const, content: "" }];

    assistantIndexRef.current = assistantIndex;
    discardBufferedDelta();
    setMessages(nextMessages);
    setIsStreaming(true);

    try {
      const token = await getToken();
      if (!token) {
        throw new Error("登录状态已失效，请重新登录后再试");
      }

      await streamInterviewChat({
        token,
        message: content,
        signal: abortController.signal,
        onState: setProgress,
        onReport: setReport,
        onDelta: (text) => {
          deltaBufferRef.current += text;
          scheduleDeltaFlush();
        },
      });
      flushBufferedDelta();
    } catch (error) {
      if (abortController.signal.aborted) return;

      discardBufferedDelta();
      const message = error instanceof Error ? error.message : "AI 暂时无法响应，请稍后重试";
      setMessages((current) =>
        current.map((item, index) =>
          index === assistantIndex ? { ...item, content: message } : item,
        ),
      );
    } finally {
      if (!abortController.signal.aborted) {
        setIsStreaming(false);
      }
      assistantIndexRef.current = null;
    }
  }

  return (
    <section className="relative mx-auto flex h-[calc(100dvh-132px)] min-h-0 w-full max-w-5xl overflow-hidden rounded-2xl border border-black/10 bg-white shadow-lg shadow-black/5 dark:border-white/10 dark:bg-[#1c1c1a]">
      <div
        className="pointer-events-none absolute right-[5%] top-[18%] z-0 h-[350px] w-[350px] rounded-full bg-[radial-gradient(circle,rgba(83,74,183,0.08)_0%,rgba(244,63,94,0.04)_50%,transparent_100%)] blur-3xl"
        aria-hidden="true"
      />

      <div className="relative z-10 flex min-h-0 w-full flex-col">
        <header className="flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-black/10 px-5 py-3 dark:border-white/10">
          <div>
            <h1 className="bg-gradient-to-br from-[#534AB7] to-rose-600 bg-clip-text text-sm font-bold text-transparent">
              AI 模拟面试舱 · Agent Cabin
            </h1>
            <p className="mt-1 text-xs text-black/45 dark:text-white/45">
              {formatStageLabel(progress.stage)}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyChat}
              disabled={messages.length === 0}
              className="gap-1.5 border-black/10 text-xs font-medium hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/5 disabled:pointer-events-none disabled:opacity-50"
              title="复制当前全部会话内容"
            >
              {copied ? (
                <>
                  <Check className="size-3.5 text-green-600 dark:text-green-500" />
                  <span>已复制</span>
                </>
              ) : (
                <>
                  <Copy className="size-3.5 text-black/60 dark:text-white/60" />
                  <span>复制会话</span>
                </>
              )}
            </Button>
            <InterviewProgress progress={progress} />
          </div>
        </header>

        <div className="interview-chat-scroll flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-5">
          {messages.map((message, index) => (
            <MessageBubble
              key={`${message.role}-${index}`}
              message={message}
              isPending={isStreaming && index === messages.length - 1}
            />
          ))}
          {report && <ReportCard report={report} />}
          <div ref={messagesEndRef} />
        </div>

        {progress.stage === "closing" && (
          <div className="shrink-0 px-5 pb-3">
            <Button variant="outline" onClick={handleNewRound}>
              开始新一轮面试
            </Button>
          </div>
        )}
        <ChatInput onSend={handleSend} isStreaming={isStreaming} />
      </div>
    </section>
  );
}

function InterviewProgress({ progress }: { progress: InterviewProgressState }) {
  const total = Math.max(progress.total_questions, 1);
  const current = Math.min(Math.max(progress.question_count, 0), total);
  const percent = progress.stage === "closing" ? 100 : Math.round((current / total) * 100);

  return (
    <div className="flex min-w-[168px] flex-col gap-1.5" aria-label="面试进度">
      <div className="flex items-center justify-between text-xs font-medium text-black/60 dark:text-white/60">
        <span>{progress.stage === "opening" ? "准备中" : `第 ${current}/${total} 题`}</span>
        <span>{percent}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
        <div
          className="h-full rounded-full bg-[#534AB7] transition-[width] duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function formatStageLabel(stage: InterviewProgressState["stage"]) {
  if (stage === "opening") return "开场信息收集中";
  if (stage === "closing") return "本轮面试已结束";
  return "正式面试进行中";
}
```

- [ ] **Step 4: 运行所有前端测试**

```bash
cd frontend && pnpm test
```

Expected: all pass（含改动的旧测试与 4 个新测试）

- [ ] **Step 5: typecheck + build**

```bash
cd frontend && pnpm typecheck && pnpm build
```

Expected: no errors

- [ ] **Step 6: commit**

```bash
git add frontend/app/interview/_components/interview-chat.tsx frontend/app/interview/_components/interview-chat.test.tsx
git commit -m "feat(interview): 预置开场消息、closing 重置按钮与 ReportCard 内联渲染"
```
