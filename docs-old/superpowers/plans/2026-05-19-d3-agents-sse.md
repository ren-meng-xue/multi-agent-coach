# D3 - 3 Agent + SSE 流式 + Clerk JWT 鉴权（10h）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 HR / 技术 / Coach 三个真实 Agent 节点，接通 SSE 流式响应，所有 API 走 `get_current_user_id`（Clerk JWT 校验）替换 hardcode `user_id=1`，前端简陋 UI 能跑完一次"无记忆假面试"。

**Architecture:** 把 D2 占位节点替换为真实 LLM 调用：HR Agent 出行为面题、技术 Agent 调 `search_rag_by_text` 检索后出技术题、Coach Agent 给综合复盘。LangGraph `astream_events("v2")` 推 token 到 `sse-starlette` 的 `EventSourceResponse`。`interview_session` 和 `interview_message` 表记录会话（user_id 为 Clerk user_id）。前端用 `EventSource` 收 SSE。**所有 API 端点注入 `get_current_user_id`（Depends），未登录返回 401。**

**Tech Stack:** LangGraph astream_events / sse-starlette / FastAPI / Next.js EventSource / Clerj JWT 校验。

**输入：** D2 EOD commit。`rag_chunks > 100`，空图能 invoke 通。D1 Clerk PEM 占位文件存在。

**输出：** D3 EOD commit `feat: 3 Agent + SSE 流式 + Clerk auth`。浏览器能完整跑完一次面试，token 流式可见，未登录返回 401。

---

## Task 1: Agent 通用 prompt 模板

**Files:**
- Create: `backend/app/services/agents/prompts.py`
- Test: `backend/tests/unit/test_prompts.py`

- [ ] **Step 1: 写失败测试**

```python
from app.services.agents.prompts import (
    HR_SYSTEM_PROMPT,
    TECH_SYSTEM_PROMPT,
    COACH_SYSTEM_PROMPT,
    render_with_memory,
)


def test_prompts_non_empty():
    for p in (HR_SYSTEM_PROMPT, TECH_SYSTEM_PROMPT, COACH_SYSTEM_PROMPT):
        assert len(p) > 100


def test_render_with_memory_injects_profile():
    out = render_with_memory(
        HR_SYSTEM_PROMPT,
        memory={"profile": {"goals": "AI Agent 工程师"}, "relevant_stars": [], "active_weaknesses": [], "last_session_summary": None},
        rag_snippets=[],
    )
    assert "AI Agent 工程师" in out


def test_render_with_memory_handles_empty_memory():
    out = render_with_memory(HR_SYSTEM_PROMPT, memory={}, rag_snippets=[])
    assert len(out) > 100
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_prompts.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `app/services/agents/prompts.py`**

```python
HR_SYSTEM_PROMPT = """你是 Multi Agent Coach 的 HR 面试官。
你的任务是对候选人进行行为面，覆盖：自我介绍、项目背景、团队协作、动机。
风格：友好、专业、引导对方用 STAR 结构。每次只问 1 个问题，不要堆叠。
当你已经问完 2-3 题且候选人回答完整后，输出标记 `[HR_DONE]` 切换到技术面。

候选人画像（如有）：
{profile_block}

历史 STAR 故事（如有，避免重复深挖）：
{stars_block}

上一场面试摘要（如有）：
{last_summary_block}
"""

TECH_SYSTEM_PROMPT = """你是 Multi Agent Coach 的技术面试官，方向是 AI Agent 工程师。
你的考察范围：LangGraph 多 Agent 编排 / RAG 系统设计 / Eval 体系 / MemGPT 分级记忆 / Reflexion 自反思 / MCP 协议。
风格：深挖、追问 trade-off、关注落地细节而非概念背诵。每次只问 1 个问题。
当你已经问完 3-4 题且至少 1 题深入到实现细节后，输出标记 `[TECH_DONE]` 切换到复盘。

候选人画像 / 技术强弱（如有）：
{profile_block}

弱点标签（重点考察）：
{weaknesses_block}

RAG 题库参考（来自官方文档/论文，用作出题灵感而非念稿）：
{rag_block}
"""

COACH_SYSTEM_PROMPT = """你是 Multi Agent Coach 的总教练。
本场面试已完成，你的任务是给候选人一个综合复盘：总评 → 关键改进点（3 个以内）→ 鼓励 + 下次重点。
风格：直接、可执行、不说套话。先讲优势再讲改进，最后给一句"下次重点练 X"。

本场所有 Reflexion 结果（每题评分 + gaps）：
{reflexion_block}

候选人历史画像（用来对比成长曲线）：
{profile_block}
"""


def _fmt_profile(profile: dict | None) -> str:
    if not profile:
        return "（暂无）"
    lines = []
    if profile.get("goals"):
        lines.append(f"目标：{profile['goals']}")
    if profile.get("experience_summary"):
        lines.append(f"经验：{profile['experience_summary']}")
    if profile.get("tech_strengths"):
        lines.append(f"技术强项：{profile['tech_strengths']}")
    if profile.get("tech_weaknesses"):
        lines.append(f"技术弱项：{profile['tech_weaknesses']}")
    return "\n".join(lines) if lines else "（暂无）"


def _fmt_stars(stars: list | None) -> str:
    if not stars:
        return "（暂无）"
    return "\n".join(
        f"- {s.get('project_name','?')}: {s.get('situation','')[:80]}" for s in stars
    )


def _fmt_weaknesses(weaknesses: list | None) -> str:
    if not weaknesses:
        return "（暂无）"
    return "\n".join(
        f"- {w.get('tag')} (severity={w.get('severity',0):.1f}, ×{w.get('occurrence_count',1)})"
        for w in weaknesses
    )


def _fmt_rag(snippets: list | None) -> str:
    if not snippets:
        return "（暂无）"
    return "\n".join(
        f"[{s.get('source','?')}] {(s.get('content','') or '')[:300]}" for s in snippets
    )


def _fmt_reflexion(items: list | None) -> str:
    if not items:
        return "（暂无）"
    return "\n".join(
        f"题 {i+1}: clarity={r.get('scores',{}).get('clarity','?')}, "
        f"depth={r.get('scores',{}).get('depth','?')}, "
        f"gaps={r.get('gaps',[])}"
        for i, r in enumerate(items)
    )


def render_with_memory(
    template: str,
    memory: dict | None = None,
    rag_snippets: list | None = None,
    reflexion_results: list | None = None,
) -> str:
    memory = memory or {}
    return template.format(
        profile_block=_fmt_profile(memory.get("profile")),
        stars_block=_fmt_stars(memory.get("relevant_stars")),
        last_summary_block=memory.get("last_session_summary") or "（暂无）",
        weaknesses_block=_fmt_weaknesses(memory.get("active_weaknesses")),
        rag_block=_fmt_rag(rag_snippets),
        reflexion_block=_fmt_reflexion(reflexion_results),
    )
```

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/unit/test_prompts.py -v
```
Expected: 3 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/agents/prompts.py backend/tests/unit/test_prompts.py
git commit -m "feat(agents): add HR/Tech/Coach system prompts with memory rendering"
```

---

## Task 2: HR Agent 节点

**Files:**
- Create: `backend/app/services/agents/nodes/hr.py`
- Test: `backend/tests/unit/test_hr_node.py`

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_hr_node_asks_first_question_when_empty_messages():
    from app.services.agents.nodes.hr import hr_node

    fake_chat = AsyncMock(
        return_value={
            "choices": [{"message": {"role": "assistant", "content": "请简单介绍一下你自己"}}]
        }
    )
    with patch("app.services.agents.nodes.hr.chat_complete", new=fake_chat):
        out = await hr_node(
            {
                "session_id": "s1",
                "user_id": 1,
                "phase": "hr",
                "messages": [],
                "user_answer": "",
                "retrieved_memory": {},
            }
        )
    assert "current_question" in out
    assert "介绍" in out["current_question"]
    assert out["phase"] == "hr"


@pytest.mark.asyncio
async def test_hr_node_switches_to_tech_when_done_marker():
    from app.services.agents.nodes.hr import hr_node

    fake_chat = AsyncMock(
        return_value={
            "choices": [
                {"message": {"role": "assistant", "content": "好的，行为面到这里。[HR_DONE]"}}
            ]
        }
    )
    with patch("app.services.agents.nodes.hr.chat_complete", new=fake_chat):
        out = await hr_node(
            {
                "session_id": "s1",
                "user_id": 1,
                "phase": "hr",
                "messages": [
                    {"role": "assistant", "content": "Q1"},
                    {"role": "user", "content": "A1"},
                    {"role": "assistant", "content": "Q2"},
                    {"role": "user", "content": "A2"},
                ],
                "user_answer": "A2",
                "retrieved_memory": {},
            }
        )
    assert out["phase"] == "tech"
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_hr_node.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `app/services/agents/nodes/hr.py`**

```python
from app.core.logging import get_logger
from app.services.agents.prompts import HR_SYSTEM_PROMPT, render_with_memory
from app.services.agents.state import InterviewState
from app.services.llm.openai_client import chat_complete

log = get_logger("app.agents.hr")


async def hr_node(state: InterviewState) -> dict:
    system = render_with_memory(HR_SYSTEM_PROMPT, memory=state.get("retrieved_memory") or {})
    history = [{"role": "system", "content": system}]
    for m in state.get("messages") or []:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "type", "user")
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        history.append({"role": role, "content": content})

    if not state.get("messages"):
        history.append({"role": "user", "content": "请开始第一题（自我介绍方向）"})
    elif state.get("user_answer"):
        history.append({"role": "user", "content": state["user_answer"]})

    resp = await chat_complete(history, temperature=0.7)
    content = resp["choices"][0]["message"]["content"]
    log.info("hr_node_response", session=state.get("session_id"), preview=content[:80])

    out: dict = {"current_question": content}
    if "[HR_DONE]" in content:
        out["phase"] = "tech"
        out["current_question"] = content.replace("[HR_DONE]", "").strip()
    else:
        out["phase"] = "hr"
    return out
```

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/unit/test_hr_node.py -v
```
Expected: 2 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/agents/nodes/hr.py backend/tests/unit/test_hr_node.py
git commit -m "feat(agents): implement HR agent node with phase switch marker"
```

---

## Task 3: 技术 Agent 节点（接 RAG）

**Files:**
- Create: `backend/app/services/agents/nodes/tech.py`
- Test: `backend/tests/unit/test_tech_node.py`

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_tech_node_retrieves_rag_and_asks_question():
    from app.services.agents.nodes.tech import tech_node

    fake_chunks = [
        MagicMock(source="langgraph", content="LangGraph supports multi agent ...", title="x")
    ]
    fake_chat = AsyncMock(
        return_value={
            "choices": [
                {"message": {"role": "assistant", "content": "请讲讲 LangGraph 的 StateGraph 如何持久化"}}
            ]
        }
    )
    with patch(
        "app.services.agents.nodes.tech.search_rag_by_text", new=AsyncMock(return_value=fake_chunks)
    ), patch("app.services.agents.nodes.tech.chat_complete", new=fake_chat):
        out = await tech_node(
            {
                "session_id": "s1",
                "user_id": 1,
                "phase": "tech",
                "messages": [{"role": "user", "content": "我熟悉 LangGraph"}],
                "user_answer": "我熟悉 LangGraph",
                "retrieved_memory": {"profile": {"tech_strengths": {"LangGraph": 0.7}}},
            }
        )
    assert "current_question" in out
    assert out["phase"] in {"tech", "reflexion"}
    assert "retrieved_rag" in out


@pytest.mark.asyncio
async def test_tech_node_switches_to_reflexion_on_done_marker():
    from app.services.agents.nodes.tech import tech_node

    fake_chat = AsyncMock(
        return_value={"choices": [{"message": {"content": "好，到这里 [TECH_DONE]"}}]}
    )
    with patch(
        "app.services.agents.nodes.tech.search_rag_by_text", new=AsyncMock(return_value=[])
    ), patch("app.services.agents.nodes.tech.chat_complete", new=fake_chat):
        out = await tech_node(
            {
                "session_id": "s1",
                "user_id": 1,
                "phase": "tech",
                "messages": [{"role": "user", "content": "answered 4 questions"}] * 4,
                "user_answer": "answered",
                "retrieved_memory": {},
            }
        )
    assert out["phase"] == "reflexion"
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_tech_node.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `app/services/agents/nodes/tech.py`**

```python
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.services.agents.prompts import TECH_SYSTEM_PROMPT, render_with_memory
from app.services.agents.state import InterviewState
from app.services.llm.openai_client import chat_complete
from app.services.rag.retrieve import search_rag_by_text

log = get_logger("app.agents.tech")


async def tech_node(state: InterviewState) -> dict:
    query = state.get("user_answer") or "AI Agent 工程师面试 LangGraph RAG"
    async with async_session_factory() as db:
        chunks = await search_rag_by_text(db, query, top_k=5)
    rag_snippets = [
        {"source": c.source, "content": c.content, "title": c.title} for c in chunks
    ]

    system = render_with_memory(
        TECH_SYSTEM_PROMPT,
        memory=state.get("retrieved_memory") or {},
        rag_snippets=rag_snippets,
    )
    history = [{"role": "system", "content": system}]
    for m in state.get("messages") or []:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "type", "user")
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        history.append({"role": role, "content": content})
    if state.get("user_answer"):
        history.append({"role": "user", "content": state["user_answer"]})
    if not state.get("messages"):
        history.append({"role": "user", "content": "请开始第一题（围绕候选人提到的技术深挖）"})

    resp = await chat_complete(history, temperature=0.6)
    content = resp["choices"][0]["message"]["content"]
    log.info("tech_node_response", session=state.get("session_id"), preview=content[:80])

    out: dict = {
        "current_question": content,
        "retrieved_rag": rag_snippets,
    }
    if "[TECH_DONE]" in content:
        out["phase"] = "reflexion"
        out["current_question"] = content.replace("[TECH_DONE]", "").strip()
    else:
        out["phase"] = "tech"
    return out
```

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/unit/test_tech_node.py -v
```
Expected: 2 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/agents/nodes/tech.py backend/tests/unit/test_tech_node.py
git commit -m "feat(agents): implement tech agent node with RAG retrieval"
```

---

## Task 4: Coach Agent 节点

**Files:**
- Create: `backend/app/services/agents/nodes/coach.py`
- Test: `backend/tests/unit/test_coach_node.py`

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_coach_node_produces_summary_and_marks_done():
    from app.services.agents.nodes.coach import coach_node

    fake_chat = AsyncMock(
        return_value={"choices": [{"message": {"content": "总评：整体不错。改进：补量化。下次重点：系统设计。"}}]}
    )
    with patch("app.services.agents.nodes.coach.chat_complete", new=fake_chat):
        out = await coach_node(
            {
                "session_id": "s1",
                "user_id": 1,
                "phase": "coach",
                "messages": [],
                "retrieved_memory": {},
                "reflexion_result": {"items": []},
            }
        )
    assert out["phase"] == "done"
    assert "current_question" in out
    assert "改进" in out["current_question"]
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_coach_node.py -v
```
Expected: FAIL。

- [ ] **Step 3: 实现 `app/services/agents/nodes/coach.py`**

```python
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.agents.prompts import COACH_SYSTEM_PROMPT, render_with_memory
from app.services.agents.state import InterviewState
from app.services.llm.openai_client import chat_complete

log = get_logger("app.agents.coach")


async def coach_node(state: InterviewState) -> dict:
    reflexion_items = (state.get("reflexion_result") or {}).get("items", []) or []
    system = render_with_memory(
        COACH_SYSTEM_PROMPT,
        memory=state.get("retrieved_memory") or {},
        reflexion_results=reflexion_items,
    )
    history = [
        {"role": "system", "content": system},
        {"role": "user", "content": "请输出本场的综合复盘"},
    ]
    resp = await chat_complete(
        history, model=get_settings().openai_model_coach, temperature=0.5
    )
    content = resp["choices"][0]["message"]["content"]
    log.info("coach_summary", session=state.get("session_id"), preview=content[:80])
    return {"current_question": content, "phase": "done"}
```

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/unit/test_coach_node.py -v
```
Expected: 1 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/agents/nodes/coach.py backend/tests/unit/test_coach_node.py
git commit -m "feat(agents): implement coach agent node for final recap"
```

---

## Task 5: 替换占位节点 + 简化的 reflexion/memory_writer

**Files:**
- Modify: `backend/app/services/agents/graph.py`
- Create: `backend/app/services/agents/nodes/reflexion.py` (D3 简化版，只是 noop，D5 替换)
- Create: `backend/app/services/agents/nodes/memory_writer.py` (D3 noop，D4/D5 替换)

- [ ] **Step 1: 实现 D3 占位 reflexion**

`backend/app/services/agents/nodes/reflexion.py`:

```python
from app.services.agents.state import InterviewState


async def reflexion_node(state: InterviewState) -> dict:
    # D3 stub: skip reflexion，留待 D5 真实实现
    return {"phase": "memory_writer", "reflexion_result": {"items": []}}
```

- [ ] **Step 2: 实现 D3 占位 memory_writer**

`backend/app/services/agents/nodes/memory_writer.py`:

```python
from app.services.agents.state import InterviewState


async def memory_writer_node(state: InterviewState) -> dict:
    # D3 stub：D4 改为读 L2，D5 改为写 L2/L3/L4
    return {"phase": "coach"}
```

- [ ] **Step 3: 改 `app/services/agents/graph.py`**

```python
from langgraph.graph import END, START, StateGraph

from app.services.agents.nodes.coach import coach_node
from app.services.agents.nodes.hr import hr_node
from app.services.agents.nodes.memory_writer import memory_writer_node
from app.services.agents.nodes.reflexion import reflexion_node
from app.services.agents.nodes.tech import tech_node
from app.services.agents.state import InterviewState


def build_graph():
    g = StateGraph(InterviewState)
    g.add_node("hr_agent", hr_node)
    g.add_node("tech_agent", tech_node)
    g.add_node("reflexion", reflexion_node)
    g.add_node("memory_writer", memory_writer_node)
    g.add_node("coach_agent", coach_node)

    g.add_edge(START, "hr_agent")
    g.add_edge("hr_agent", "tech_agent")
    g.add_edge("tech_agent", "reflexion")
    g.add_edge("reflexion", "memory_writer")
    g.add_edge("memory_writer", "coach_agent")
    g.add_edge("coach_agent", END)
    return g.compile()
```

> 注意：D2 的 `test_graph_compiles_and_runs_empty` 测试现在会调用真实 LLM —— 改用 mock。

- [ ] **Step 4: 改 D2 的 graph 测试以兼容**

修改 `backend/tests/unit/test_graph.py`：

```python
from unittest.mock import AsyncMock, patch

import pytest


def test_interview_state_keys():
    from app.services.agents.state import InterviewState
    annotations = InterviewState.__annotations__
    expected = {
        "session_id", "user_id", "phase", "current_question", "user_answer",
        "retrieved_memory", "retrieved_rag", "reflexion_result", "messages",
    }
    assert expected.issubset(set(annotations.keys()))


@pytest.mark.asyncio
async def test_graph_compiles_and_runs_with_mocks():
    fake = AsyncMock(
        return_value={"choices": [{"message": {"content": "[HR_DONE] question"}}]}
    )
    with patch("app.services.agents.nodes.hr.chat_complete", new=fake), \
         patch("app.services.agents.nodes.tech.chat_complete", new=fake), \
         patch("app.services.agents.nodes.coach.chat_complete", new=fake), \
         patch("app.services.agents.nodes.tech.search_rag_by_text", new=AsyncMock(return_value=[])):
        from app.services.agents.graph import build_graph
        graph = build_graph()
        out = await graph.ainvoke(
            {
                "session_id": "s1", "user_id": 1, "phase": "hr",
                "current_question": "", "user_answer": "answer",
                "retrieved_memory": {}, "retrieved_rag": [],
                "reflexion_result": {}, "messages": [],
            }
        )
    assert out["phase"] == "done"
```

> ⚠️ `user_id` 已从 D1 起改为 string（Clerk user_id）。所有涉及 `user_id` 的测试 mock/fixture 统一用 `"user_test01abc"` 而非 `1`。

- [ ] **Step 5: 跑测试**

```bash
cd backend && uv run pytest tests/unit/test_graph.py -v
```
Expected: 2 passed。

- [ ] **Step 6: commit**

```bash
git add backend/app/services/agents/graph.py backend/app/services/agents/nodes/reflexion.py backend/app/services/agents/nodes/memory_writer.py backend/tests/unit/test_graph.py
git commit -m "feat(agents): wire real HR/Tech/Coach nodes into graph (D5 reflexion stub)"
```

---

## Task 6: Interview Schemas + Repository helpers

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/interview.py`
- Create: `backend/app/services/interview_repo.py`
- Test: `backend/tests/integration/test_interview_repo.py`

- [ ] **Step 1: 写 Pydantic schemas**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class StartInterviewResponse(BaseModel):
    session_id: uuid.UUID
    first_question: str


class AnswerRequest(BaseModel):
    user_answer: str


class InterviewMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class InterviewReport(BaseModel):
    session_id: uuid.UUID
    summary: str | None
    scores: dict | None
    messages: list[InterviewMessageOut]
```

- [ ] **Step 2: 写失败测试**

```python
import pytest

from app.services.interview_repo import (
    append_message,
    create_session,
    end_session,
    get_session,
    list_messages,
)


@pytest.mark.asyncio
async def test_create_and_get_session(db):
    s = await create_session(db, user_id=1)
    await db.flush()
    got = await get_session(db, s.id)
    assert got is not None
    assert got.user_id == 1


@pytest.mark.asyncio
async def test_append_and_list_messages(db):
    s = await create_session(db, user_id=1)
    await db.flush()
    await append_message(db, s.id, role="hr_agent", content="Q1")
    await append_message(db, s.id, role="user", content="A1")
    await db.flush()
    msgs = await list_messages(db, s.id)
    assert len(msgs) == 2
    assert msgs[0].role == "hr_agent"
    assert msgs[1].role == "user"


@pytest.mark.asyncio
async def test_end_session_sets_ended_at(db):
    s = await create_session(db, user_id=1)
    await db.flush()
    await end_session(db, s.id, summary="ok", scores={"clarity": 7})
    await db.flush()
    got = await get_session(db, s.id)
    assert got.ended_at is not None
    assert got.summary == "ok"
```

- [ ] **Step 3: 跑失败测试**

```bash
cd backend && uv run pytest tests/integration/test_interview_repo.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 4: 实现 `app/services/interview_repo.py`**

```python
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models.core import InterviewMessage, InterviewSession


async def create_session(db: AsyncSession, user_id: int) -> InterviewSession:
    s = InterviewSession(user_id=user_id)
    db.add(s)
    await db.flush()
    return s


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> InterviewSession | None:
    result = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    return result.scalar_one_or_none()


async def append_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: str,
    retrieved_context: dict | None = None,
    reflexion_payload: dict | None = None,
) -> InterviewMessage:
    m = InterviewMessage(
        session_id=session_id,
        role=role,
        content=content,
        retrieved_context=retrieved_context,
        reflexion_payload=reflexion_payload,
    )
    db.add(m)
    await db.flush()
    return m


async def list_messages(db: AsyncSession, session_id: uuid.UUID) -> Sequence[InterviewMessage]:
    result = await db.execute(
        select(InterviewMessage)
        .where(InterviewMessage.session_id == session_id)
        .order_by(InterviewMessage.created_at)
    )
    return list(result.scalars().all())


async def end_session(
    db: AsyncSession, session_id: uuid.UUID, summary: str | None, scores: dict | None
) -> None:
    s = await get_session(db, session_id)
    if s:
        s.ended_at = func.now()
        s.summary = summary
        s.scores = scores
        await db.flush()
```

- [ ] **Step 5: 跑测试**

```bash
cd backend && uv run pytest tests/integration/test_interview_repo.py -v
```
Expected: 3 passed。

- [ ] **Step 6: commit**

```bash
git add backend/app/schemas/__init__.py backend/app/schemas/interview.py backend/app/services/interview_repo.py backend/tests/integration/test_interview_repo.py
git commit -m "feat(interview): add schemas and session/message repo"
```

---

## Task 7: 所有 API 接 Clerk auth（新增，D3 全局）

> 以下改动影响 D3 所有后续 Task 的测试。核心原则：所有 API endpoint 用 `user_id: str = Depends(get_current_user_id)` 替代 `user_id: int = 1`；所有集成测试用 `monkeypatch` mock `get_current_user_id` 或传 `Authorization: Bearer fake-jwt` header。

**Files:**
- Create: `backend/tests/auth_fixtures.py`（测试用 auth mock helper）

- [ ] **Step 1: 写测试用 auth mock helper**

```python
# backend/tests/auth_fixtures.py
"""统一的 Clerk auth mock，供所有集成测试复用。"""
import jwt
from unittest.mock import patch


FAKE_USER_ID = "user_test01abc"
FAKE_PEM = "fake-pem-for-test"


def make_test_jwt(sub: str = FAKE_USER_ID) -> str:
    """生成一个假 JWT 用于集成测试（不需要真 PEM）。"""
    return jwt.encode({"sub": sub}, "secret", algorithm="HS256")


async def fake_get_current_user_id():
    """替代 get_current_user_id 的 async stub。"""
    return FAKE_USER_ID


def patch_auth():
    """patch FastAPI Depends(get_current_user_id) 到 fake。"""
    return patch(
        "app.core.auth.get_current_user_id",
        return_value=FAKE_USER_ID,
    )
```

- [ ] **Step 2: 所有集成测试统一用法**

```python
# 方式 1：monkeypatch（推荐）
@pytest.mark.asyncio
async def test_something(monkeypatch):
    from app.tests.auth_fixtures import patch_auth
    with patch_auth():
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/v1/interview/start")
    assert r.status_code == 200

# 方式 2：直接传 Authorization header
@pytest.mark.asyncio
async def test_unauthorized_rejected():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/v1/interview/start")  # 没有 header
    assert r.status_code == 422  # FastAPI 校验 Header 必填
```

- [ ] **Step 3: commit**

```bash
git add backend/tests/auth_fixtures.py
git commit -m "test(auth): add Clerk JWT mock helper"
```

> ⚠️ D3/D4/D5/D6 所有集成测试的 API 调用都必须走 auth mock。以下各 Task 的测试片段中 `user_id=1` 和 `json={"user_id": 1}` 的调用方式需替换为上述 patterns。

---

## Task 8: SSE 流式 API（/interview/start + /answer）

**Files:**
- Create: `backend/app/api/v1/interview.py`
- Modify: `backend/app/main.py`（include router）
- Test: `backend/tests/integration/test_interview_api.py`

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_start_interview_returns_session_and_first_question():
    fake = AsyncMock(
        return_value={"choices": [{"message": {"content": "请介绍一下你自己"}}]}
    )
    with patch("app.services.agents.nodes.hr.chat_complete", new=fake):
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test",
                               headers={"Authorization": "Bearer fake-jwt"}) as ac:
            r = await ac.post("/api/v1/interview/start")
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert "first_question" in data
    assert "介绍" in data["first_question"]


@pytest.mark.asyncio
async def test_answer_endpoint_streams_sse():
    fake = AsyncMock(
        return_value={"choices": [{"message": {"content": "继续下一题"}}]}
    )
    with patch("app.services.agents.nodes.hr.chat_complete", new=fake), \
         patch("app.services.agents.nodes.tech.chat_complete", new=fake), \
         patch("app.services.agents.nodes.coach.chat_complete", new=fake), \
         patch("app.services.agents.nodes.tech.search_rag_by_text", new=AsyncMock(return_value=[])):
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", timeout=30) as ac:
            start = await ac.post("/api/v1/interview/start", json={"user_id": 1})
            sid = start.json()["session_id"]
            r = await ac.post(f"/api/v1/interview/{sid}/answer", json={"user_answer": "我擅长 LangGraph"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    body = r.text
    assert "data:" in body  # SSE 标志
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/integration/test_interview_api.py -v
```
Expected: FAIL（路由还没注册）。

- [ ] **Step 3: 实现 `app/api/v1/interview.py`**

```python
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.auth import get_current_user_id
from app.core.logging import get_logger
from app.db.session import async_session_factory, get_db
from app.schemas.interview import (
    AnswerRequest,
    StartInterviewResponse,
)
from app.services.agents.graph import build_graph
from app.services.agents.nodes.hr import hr_node
from app.services.interview_repo import (
    append_message,
    create_session,
    end_session,
    get_session,
    list_messages,
)

router = APIRouter()
log = get_logger("app.api.interview")


@router.post("/interview/start", response_model=StartInterviewResponse)
async def start_interview(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    session = await create_session(db, user_id=user_id)
    # 直接调用 HR node 拿第一题
    initial_state = {
        "session_id": str(session.id),
        "user_id": body.user_id,
        "phase": "hr",
        "messages": [],
        "user_answer": "",
        "retrieved_memory": {},
    }
    result = await hr_node(initial_state)
    first_q = result["current_question"]
    await append_message(db, session.id, role="hr_agent", content=first_q)
    await db.commit()
    return StartInterviewResponse(session_id=session.id, first_question=first_q)


@router.post("/interview/{session_id}/answer")
async def answer(session_id: uuid.UUID, body: AnswerRequest):
    """SSE 流式回答。处理用户答案后推 Agent 的下一题；如果到达 coach 阶段，推完整复盘。"""

    async def event_generator():
        async with async_session_factory() as db:
            s = await get_session(db, session_id)
            if s is None:
                yield {"event": "error", "data": json.dumps({"detail": "session not found"})}
                return
            await append_message(db, session_id, role="user", content=body.user_answer)
            await db.commit()
            msgs = await list_messages(db, session_id)

        history = [{"role": m.role if m.role == "user" else "assistant", "content": m.content} for m in msgs]

        graph = build_graph()
        state = {
            "session_id": str(session_id),
            "user_id": s.user_id,
            "phase": "hr" if len([m for m in msgs if m.role.endswith("_agent")]) < 3 else "tech",
            "messages": history,
            "user_answer": body.user_answer,
            "retrieved_memory": {},
            "retrieved_rag": [],
            "reflexion_result": {},
        }

        try:
            async for event in graph.astream_events(state, version="v2"):
                kind = event["event"]
                name = event.get("name", "")
                if kind == "on_chain_end" and name in {"hr_agent", "tech_agent", "coach_agent"}:
                    out = event["data"].get("output") or {}
                    q = out.get("current_question")
                    phase = out.get("phase")
                    if q:
                        async with async_session_factory() as db2:
                            await append_message(db2, session_id, role=name, content=q)
                            await db2.commit()
                        yield {
                            "event": "agent_message",
                            "data": json.dumps({"role": name, "content": q, "phase": phase}),
                        }
                    if phase == "done":
                        async with async_session_factory() as db3:
                            await end_session(db3, session_id, summary=q, scores=None)
                            await db3.commit()
                        yield {"event": "done", "data": json.dumps({"phase": "done"})}
                        return
        except Exception as exc:
            log.exception("interview_stream_error", session=str(session_id), error=str(exc))
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}

    return EventSourceResponse(event_generator())


@router.get("/interview/{session_id}/report")
async def get_report(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    s = await get_session(db, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    msgs = await list_messages(db, session_id)
    return {
        "session_id": session_id,
        "summary": s.summary,
        "scores": s.scores,
        "messages": [
            {"id": str(m.id), "role": m.role, "content": m.content, "created_at": m.created_at}
            for m in msgs
        ],
    }
```

- [ ] **Step 4: 注册路由 to main.py**

```python
# 在 app/main.py 加：
from app.api.v1 import interview as interview_v1
app.include_router(interview_v1.router, prefix="/api/v1", tags=["interview"])
```

- [ ] **Step 5: 跑测试**

```bash
cd backend && uv run pytest tests/integration/test_interview_api.py -v
```
Expected: 2 passed。

- [ ] **Step 6: commit**

```bash
git add backend/app/api/v1/interview.py backend/app/main.py backend/tests/integration/test_interview_api.py
git commit -m "feat(api): add /interview/start and SSE /answer endpoints"
```

---

## Task 9: 前端简陋聊天 UI

**Files:**
- Create: `frontend/lib/sse.ts`
- Modify: `frontend/app/page.tsx`
- Create: `frontend/app/interview/[sessionId]/page.tsx`

- [ ] **Step 1: 写 `frontend/lib/sse.ts`**

```typescript
export type SSEEvent = {
  event: string;
  data: any;
};

export async function* readSse(url: string, init: RequestInit): AsyncGenerator<SSEEvent> {
  const resp = await fetch(url, init);
  if (!resp.ok || !resp.body) throw new Error(`SSE failed: ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split(/\r?\n\r?\n/);
    buf = lines.pop() || "";
    for (const block of lines) {
      const evMatch = block.match(/^event:\s*(.+)$/m);
      const dataMatch = block.match(/^data:\s*(.+)$/m);
      if (!dataMatch) continue;
      let parsed: any;
      try {
        parsed = JSON.parse(dataMatch[1]);
      } catch {
        parsed = dataMatch[1];
      }
      yield { event: evMatch?.[1] || "message", data: parsed };
    }
  }
}
```

- [ ] **Step 2: 改 `frontend/app/page.tsx`**

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function start() {
    setLoading(true);
    const r = await fetch("/api/backend/v1/interview/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: 1 }),
    });
    const data = await r.json();
    router.push(`/interview/${data.session_id}?q=${encodeURIComponent(data.first_question)}`);
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-md space-y-4 text-center">
        <h1 className="text-3xl font-bold">Multi Agent Coach</h1>
        <p className="text-muted-foreground">AI Agent 工程师面试陪练</p>
        <Button onClick={start} disabled={loading} size="lg">
          {loading ? "正在开场..." : "开始面试"}
        </Button>
      </div>
    </main>
  );
}
```

- [ ] **Step 3: 写 `frontend/app/interview/[sessionId]/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { readSse } from "@/lib/sse";

type Msg = { role: string; content: string };

export default function InterviewPage() {
  const { sessionId } = useParams() as { sessionId: string };
  const sp = useSearchParams();
  const firstQ = sp.get("q") || "";
  const [messages, setMessages] = useState<Msg[]>(firstQ ? [{ role: "hr_agent", content: firstQ }] : []);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [done, setDone] = useState(false);

  async function send() {
    if (!input.trim() || streaming) return;
    const userMsg = { role: "user", content: input };
    setMessages((p) => [...p, userMsg]);
    setStreaming(true);
    const body = JSON.stringify({ user_answer: input });
    setInput("");
    try {
      for await (const ev of readSse(`/api/backend/v1/interview/${sessionId}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body,
      })) {
        if (ev.event === "agent_message") {
          setMessages((p) => [...p, { role: ev.data.role, content: ev.data.content }]);
        } else if (ev.event === "done") {
          setDone(true);
        }
      }
    } finally {
      setStreaming(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-6 space-y-4">
      <h2 className="text-xl font-semibold">面试中（session {sessionId.slice(0, 8)}）</h2>
      <div className="space-y-3 min-h-[400px]">
        {messages.map((m, i) => (
          <div key={i} className={`rounded-lg p-3 ${m.role === "user" ? "bg-blue-100 ml-12" : "bg-zinc-100 mr-12"}`}>
            <div className="text-xs text-muted-foreground mb-1">{m.role}</div>
            <div className="whitespace-pre-wrap">{m.content}</div>
          </div>
        ))}
        {streaming && <div className="text-sm text-muted-foreground">Agent 思考中…</div>}
        {done && <div className="text-sm text-green-600 font-medium">✅ 面试结束</div>}
      </div>
      {!done && (
        <div className="flex gap-2">
          <Textarea value={input} onChange={(e) => setInput(e.target.value)} placeholder="输入你的回答..." rows={3} />
          <Button onClick={send} disabled={streaming || !input.trim()}>发送</Button>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 4: 端到端浏览器验证**

```bash
./dev.sh &
sleep 8
open http://localhost:3000
```
然后：
1. 点击「开始面试」→ 跳到 `/interview/<sid>`，看到第一题
2. 输入回答 → 点发送 → 看到 SSE 流式返回 Agent 下一题
3. 连续 3-5 题后 Agent 输出 `[HR_DONE]` 切技术面，再之后切 coach
4. 最后页面显示「✅ 面试结束」

如果 SSE 不工作：用 DevTools Network 看 `/api/backend/v1/interview/<sid>/answer` 响应头是否 `Content-Type: text/event-stream`。

- [ ] **Step 5: commit**

```bash
git add frontend/lib/sse.ts frontend/app/page.tsx frontend/app/interview/
git commit -m "feat(frontend): add minimal interview chat UI with SSE streaming"
```

---

## Task 10: D3 EOD 验收 + commit

- [ ] **Step 1: 跑全部测试**

```bash
cd backend && uv run pytest -v
```
Expected: D1+D2 22 + D3（prompts 3 + hr 2 + tech 2 + coach 1 + graph 2 改 + repo 3 + api 2 = 15）共 ~37 个全绿。

- [ ] **Step 2: 验收清单核对**

- [ ] 3 个 Agent 节点真实调用 LLM
- [ ] LangGraph `astream_events` 推 SSE 正常
- [ ] `POST /interview/start` 返回 session_id + first_question
- [ ] `POST /interview/{sid}/answer` 返回 SSE
- [ ] `GET /interview/{sid}/report` 返回会话报告
- [ ] 前端能完整跑一次面试（HR → 技术 → Coach）
- [ ] 浏览器看得到 token 推送
- [ ] D3 里程碑：浏览器能完整跑完一次"无记忆假面试"

- [ ] **Step 3: 标记 D3 完成**

```bash
git commit --allow-empty -m "feat: D3 EOD - 3 Agent + SSE 流式 ✅"
git push
```

---

## 风险与延期预案（D3 专用）

| 风险 | 预案 |
|---|---|
| `astream_events` v2 API 不兼容 | 退回 `astream(stream_mode="messages")`；只关心 chain_end 事件名 |
| SSE 跨域被浏览器拦 | 已通过 `next.config.ts` rewrites 代理；如果直连 8000 出错，把 `CORS_ORIGINS` 加上 `http://localhost:3000` |
| Tech Agent RAG 检索为空（D2 seed 没跑成功） | 兜底：tech_node 检测 `len(chunks)==0` 时改用通用题库（hardcode 5 题作为 backup） |
| Coach 用 gpt-4o-mini 输出过短 | 把 model 改回 gpt-4o；预算 ~50K token/天 ≈ $0.25 |
| LangGraph 节点 reducer 报错 | `messages` 字段必须用 `Annotated[list, add_messages]`；如改了字段名要同步改 reducer |
| SSE 在 `httpx` 测试里读不到流 | 测试用 `await ac.post(...)` + `r.text` 读完整 body 即可，无需流式读取 |

如果 EOD 前 Task 8（前端 UI）未完成，**最低要求**：用 curl 验证 SSE 能返回。前端 UI 可挪到 D6 一起做（但 D4 集成 demo 验证会更费力）。
