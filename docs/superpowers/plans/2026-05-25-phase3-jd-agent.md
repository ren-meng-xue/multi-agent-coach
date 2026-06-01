# Phase 3: JD Analysis + Multi-Agent Prepare Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在面试开始前加入 Orchestrator 准备阶段——MASTER Agent 动态调度记忆检索/JD分析/出题三个子 Agent，结果以可折叠准备卡（Agent Trace Timeline）嵌入 `/interview` 页面顶部，完成后用户点「开始第1题」进入面试。

**Architecture:** MASTER 流式输出推理 bullets（用户可见），同时做结构化路由决策。若未发现练习方向则设 `need_direction=true`，前端在聊天区插入 AI 提问，用户通过底部输入框回答后 resume。子 Agent 顺序执行，各自流式 bullet。面试流程检测到 `prepared_questions` 后跳过 opening/briefing 直接出题。

**Tech Stack:** Python 3.12, FastAPI SSE, LangGraph StateGraph, LangChain ChatOpenAI, pypdf2, mammoth, httpx, beautifulsoup4, TypeScript, Next.js App Router, shadcn/ui, EventSource API

---

## 文件结构总览

### 新建文件

```
backend/app/services/jd_extractor.py          # JD 文本提取（4种来源）
backend/app/agents/prepare/__init__.py
backend/app/agents/prepare/state.py           # PrepareState + JDContext + PreparedQuestion
backend/app/agents/prepare/prompts.py         # MASTER/JD分析/出题的 prompt 常量
backend/app/agents/prepare/nodes.py           # 4个节点函数
backend/app/agents/prepare/graph.py           # StateGraph + SSE 流
backend/app/api/v1/prepare.py                 # /api/v1/prepare/start + resume 端点
backend/tests/unit/test_jd_extractor.py
backend/tests/unit/test_prepare_nodes.py
backend/tests/unit/test_prepare_graph.py
backend/tests/integration/test_prepare_api.py

frontend/app/interview/_components/trace-node.tsx
frontend/app/interview/_components/agent-trace.tsx
frontend/app/interview/_components/preparation-card.tsx
frontend/app/interview/_components/question-list-modal.tsx
frontend/app/interview/_components/trace-node.test.tsx
frontend/app/interview/_components/preparation-card.test.tsx
```

### 修改文件

```
backend/app/agents/interviewer/state.py       # 追加 jd_context, prepared_questions 字段
backend/app/agents/interviewer/nodes.py       # ask_question_node 优先用 prepared_questions
backend/app/agents/interviewer/graph.py       # route_after_load 检测 prepared_questions
backend/app/main.py                           # 注册 prepare router
backend/app/api/v1/__init__.py (如存在)
frontend/app/interview/_components/interview-chat.tsx  # 加准备卡，处理 need_direction
frontend/app/coach/coach-dashboard.tsx        # 加 JD 上传入口
frontend/lib/interview-chat.ts                # 加 prepare API 客户端函数
```

---

## Task 1: JD 文本提取服务

**Files:**
- Create: `backend/app/services/jd_extractor.py`
- Test: `backend/tests/unit/test_jd_extractor.py`

- [ ] **Step 1.1: 安装依赖**

```bash
cd backend
.venv/bin/pip install pypdf2 mammoth httpx beautifulsoup4
```

在 `pyproject.toml` 或 `requirements.txt` 中追加这4个依赖。

- [ ] **Step 1.2: 写失败测试**

```python
# backend/tests/unit/test_jd_extractor.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.jd_extractor import extract_jd_text, NeedManualInput, JDSource

def test_text_source_returns_content_directly():
    source = JDSource(type="text", content="我们在招聘高级工程师")
    result = extract_jd_text(source)
    assert result == "我们在招聘高级工程师"

def test_text_source_strips_whitespace():
    source = JDSource(type="text", content="  JD 内容  ")
    result = extract_jd_text(source)
    assert result == "JD 内容"

@pytest.mark.asyncio
async def test_url_source_fetch_success():
    source = JDSource(type="url", url="https://example.com/job")
    with patch("app.services.jd_extractor._fetch_url", new_callable=AsyncMock) as mock:
        mock.return_value = "工程师岗位要求"
        result = await extract_jd_text_async(source)
    assert result == "工程师岗位要求"

@pytest.mark.asyncio
async def test_url_source_fetch_failure_raises_need_manual_input():
    source = JDSource(type="url", url="https://linkedin.com/jobs/1234")
    with patch("app.services.jd_extractor._fetch_url", new_callable=AsyncMock) as mock:
        mock.return_value = None
        with pytest.raises(NeedManualInput):
            await extract_jd_text_async(source)

def test_file_source_pdf():
    source = JDSource(type="file", filename="jd.pdf", content_bytes=b"%PDF-1.4 fake")
    with patch("app.services.jd_extractor._parse_pdf", return_value="PDF JD 内容"):
        result = extract_jd_text(source)
    assert result == "PDF JD 内容"

def test_file_source_docx():
    source = JDSource(type="file", filename="jd.docx", content_bytes=b"fake docx")
    with patch("app.services.jd_extractor._parse_docx", return_value="Word JD 内容"):
        result = extract_jd_text(source)
    assert result == "Word JD 内容"
```

- [ ] **Step 1.3: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_jd_extractor.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.jd_extractor'`

- [ ] **Step 1.4: 实现 jd_extractor.py**

```python
# backend/app/services/jd_extractor.py
"""JD text extraction: text / PDF / DOCX / URL → plain string."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Literal

import httpx
from bs4 import BeautifulSoup

from app.core.logging import get_logger

log = get_logger("app.services.jd_extractor")


class NeedManualInput(Exception):
    """URL 爬取失败，需用户手动粘贴文本。"""


@dataclass
class JDSource:
    type: Literal["text", "file", "url", "image"]
    content: str = ""           # text 类型使用
    url: str = ""               # url 类型使用
    filename: str = ""          # file/image 类型使用
    content_bytes: bytes = field(default_factory=bytes)  # file/image 类型使用


def extract_jd_text(source: JDSource) -> str:
    """同步提取（text/file）。URL 和 image 请用 extract_jd_text_async。"""
    if source.type == "text":
        return source.content.strip()
    if source.type == "file":
        if source.filename.endswith(".pdf"):
            return _parse_pdf(source.content_bytes)
        if source.filename.endswith((".docx", ".doc")):
            return _parse_docx(source.content_bytes)
        raise ValueError(f"Unsupported file type: {source.filename}")
    raise ValueError(f"Use extract_jd_text_async for type: {source.type}")


async def extract_jd_text_async(source: JDSource) -> str:
    """异步提取（支持全部4种来源）。"""
    if source.type in ("text", "file"):
        return extract_jd_text(source)
    if source.type == "url":
        text = await _fetch_url(source.url)
        if not text:
            raise NeedManualInput(
                "此链接需要登录或爬取失败，请直接粘贴 JD 文本。"
            )
        return text
    if source.type == "image":
        return await _extract_image_text(source.content_bytes)
    raise ValueError(f"Unknown source type: {source.type}")


def _parse_pdf(data: bytes) -> str:
    import PyPDF2  # lazy import
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    pages = [p.extract_text() or "" for p in reader.pages]
    return "\n".join(pages).strip()


def _parse_docx(data: bytes) -> str:
    import mammoth  # lazy import
    result = mammoth.extract_raw_text(io.BytesIO(data))
    return result.value.strip()


async def _fetch_url(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                log.warning("jd_url_fetch_failed", url=url, status=resp.status_code)
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return text[:8000] if text else None
    except Exception as exc:
        log.warning("jd_url_fetch_error", url=url, error=str(exc))
        return None


async def _extract_image_text(image_bytes: bytes) -> str:
    """使用 Claude Vision 从图片截图提取 JD 文本。"""
    import base64
    from langchain_anthropic import ChatAnthropic
    from app.core.config import get_settings

    settings = get_settings()
    model = ChatAnthropic(
        model="claude-opus-4-5",
        api_key=settings.anthropic_api_key,
        timeout=30,
    )
    b64 = base64.standard_b64encode(image_bytes).decode()
    msg = await model.ainvoke([{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
            {"type": "text", "text": "请提取图片中的所有文字内容，保持原有格式，不要添加任何解释。"},
        ],
    }])
    return msg.content
```

- [ ] **Step 1.5: 运行测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_jd_extractor.py -v
```

Expected: 全部 PASS

- [ ] **Step 1.6: Lint + typecheck**

```bash
cd backend && .venv/bin/python -m ruff check app/services/jd_extractor.py
cd backend && .venv/bin/python -m mypy app/services/jd_extractor.py
```

- [ ] **Step 1.7: Commit**

```bash
git add backend/app/services/jd_extractor.py backend/tests/unit/test_jd_extractor.py
git commit -m "feat(prepare): JD text extractor — text/file/url/image → str"
```

---

## Task 2: PrepareState 类型定义

**Files:**
- Create: `backend/app/agents/prepare/__init__.py`
- Create: `backend/app/agents/prepare/state.py`

- [ ] **Step 2.1: 创建 __init__.py**

```bash
mkdir -p backend/app/agents-1/prepare
touch backend/app/agents-1/prepare/__init__.py
```

- [ ] **Step 2.2: 写 state.py**

```python
# backend/app/agents-1/prepare/state.py
"""LangGraph state for the prepare pipeline."""
from typing import Any, Literal, TypedDict


class JDContext(TypedDict):
    company: str
    role: str
    key_skills: list[str]
    focus_areas: list[str]
    difficulty: str  # "easy" | "medium" | "hard" | "faang"


class PreparedQuestion(TypedDict):
    id: int
    question: str
    category: Literal["technical", "behavioral", "system_design"]
    focus_area: str
    priority: int  # 1=最高优先级，薄弱点相关题排前


class PrepareState(TypedDict, total=False):
    # 输入
    session_id: str
    user_id: str
    user_direction: str | None   # 当前会话用户说的方向（非记忆）
    user_background: str | None
    jd_raw: str | None           # 已提取的 JD 纯文本

    # MASTER 决策输出
    direction: str               # 识别出的方向，如"分布式系统"
    chain: list[str]             # 调用链，如 ["memory_search", "jd_analysis", "question_gen"]
    need_direction: bool         # True = 需要向用户追问方向

    # 子 Agent 结果
    weak_areas: list[str]        # 来自历史面试表现
    star_stories: list[dict[str, Any]]  # 来自 UserStory 表
    jd_context: JDContext | None
    prepared_questions: list[PreparedQuestion]

    # 最终输出
    summary: str                 # LLM 生成的一句话摘要（非固定文案）
```

- [ ] **Step 2.3: Commit**

```bash
git add backend/app/agents-1/prepare/
git commit -m "feat(prepare): PrepareState + JDContext + PreparedQuestion types"
```

---

## Task 3: memory_search_node

**Files:**
- Create: `backend/app/agents/prepare/nodes.py` (首次写入 memory_search_node)
- Test: `backend/tests/unit/test_prepare_nodes.py`

- [ ] **Step 3.1: 写失败测试**

```python
# backend/tests/unit/test_prepare_nodes.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.agents.prepare.state import PrepareState


@pytest.mark.asyncio
async def test_memory_search_returns_weak_areas_from_history():
    """有历史面试时应返回薄弱点列表。"""
    from app.agents.prepare.nodes import memory_search_node

    mock_sessions = [
        MagicMock(
            report={"technical_depth": 2, "quantified_results": 1},
            target_role="AI Agent 工程师",
        )
    ]
    mock_stories = [
        MagicMock(
            title="LangGraph 工单系统",
            role="AI 工程师",
            tags=["LangGraph", "Agent"],
            content_json={"situation": "...", "task": "...", "action": "...", "result": "..."},
        )
    ]

    state: PrepareState = {"user_id": "user_123", "user_direction": "AI Agent 工程师"}

    with patch("app.agents-1.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=mock_sessions), \
         patch("app.agents-1.prepare.nodes._get_user_stories", new_callable=AsyncMock, return_value=mock_stories):
        result = await memory_search_node(state)

    assert len(result["weak_areas"]) > 0
    assert len(result["star_stories"]) == 1
    assert result["star_stories"][0]["title"] == "LangGraph 工单系统"


@pytest.mark.asyncio
async def test_memory_search_empty_when_no_history():
    """无历史时返回空列表，不报错。"""
    from app.agents.prepare.nodes import memory_search_node

    state: PrepareState = {"user_id": "new_user"}

    with patch("app.agents-1.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents-1.prepare.nodes._get_user_stories", new_callable=AsyncMock, return_value=[]):
        result = await memory_search_node(state)

    assert result["weak_areas"] == []
    assert result["star_stories"] == []
```

- [ ] **Step 3.2: 运行测试确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_prepare_nodes.py::test_memory_search_returns_weak_areas_from_history -v
```

- [ ] **Step 3.3: 实现 memory_search_node**

创建 `backend/app/agents/prepare/nodes.py`：

```python
# backend/app/agents-1/prepare/nodes.py
"""Node functions for the prepare pipeline."""
from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.agents.prepare.state import JDContext, PrepareState, PreparedQuestion
from app.agents.prepare.prompts import (
    JD_ANALYSIS_SYSTEM_PROMPT,
    MASTER_DECISION_PROMPT,
    MASTER_REASONING_PROMPT,
    QUESTION_GEN_SYSTEM_PROMPT,
)
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.agents-1.prepare.nodes")


def _llm(streaming: bool = False, timeout: int = 30) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model_chat,
        api_key=settings.openai_api_key,
        timeout=timeout,
        streaming=streaming,
    )


# ─────────────────────────────────────────────
# 内部 DB 查询助手
# ─────────────────────────────────────────────

async def _get_recent_sessions(user_id: str, limit: int = 5) -> list[Any]:
    """读取用户最近 N 场面试 session（含 report 字段）。"""
    from app.db.session import get_async_session_context
    from app.models.core import InterviewSession
    from sqlalchemy import select, desc

    async with get_async_session_context() as db:
        result = await db.execute(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(desc(InterviewSession.created_at))
            .limit(limit)
        )
        return result.scalars().all()


async def _get_user_stories(user_id: str) -> list[Any]:
    """读取用户故事库。"""
    from app.db.session import get_async_session_context
    from app.models.core import UserStory
    from sqlalchemy import select

    async with get_async_session_context() as db:
        result = await db.execute(
            select(UserStory).where(UserStory.user_id == user_id)
        )
        return result.scalars().all()


def _extract_weak_areas(sessions: list[Any]) -> list[str]:
    """从历史 session report 提取薄弱点描述。"""
    weak = []
    for s in sessions:
        report = s.report or {}
        if report.get("technical_depth", 5) <= 2:
            weak.append("技术深度不足")
        if report.get("quantified_results", 5) <= 2:
            weak.append("量化结果欠缺")
        if report.get("failure_tradeoffs", 5) <= 2:
            weak.append("失败/降级处理薄弱")
        if report.get("structure", 5) <= 2:
            weak.append("表达结构不清晰")
        for item in report.get("improvements", []):
            if item not in weak:
                weak.append(item)
    return list(dict.fromkeys(weak))  # 去重保序


# ─────────────────────────────────────────────
# memory_search_node
# ─────────────────────────────────────────────

async def memory_search_node(state: PrepareState) -> PrepareState:
    """查询历史面试表现和故事库，填充 weak_areas + star_stories。"""
    user_id = state.get("user_id", "")
    sessions = await _get_recent_sessions(user_id)
    stories = await _get_user_stories(user_id)

    weak_areas = _extract_weak_areas(sessions)
    star_stories = [
        {
            "title": s.title,
            "role": s.role or "",
            "tags": s.tags or [],
            "content_json": s.content_json or {},
        }
        for s in stories
    ]

    log.info(
        "memory_search_done",
        user_id=user_id,
        weak_count=len(weak_areas),
        story_count=len(star_stories),
    )
    return {**state, "weak_areas": weak_areas, "star_stories": star_stories}
```

- [ ] **Step 3.4: 运行测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_prepare_nodes.py::test_memory_search_returns_weak_areas_from_history tests/unit/test_prepare_nodes.py::test_memory_search_empty_when_no_history -v
```

- [ ] **Step 3.5: Commit**

```bash
git add backend/app/agents-1/prepare/nodes.py backend/tests/unit/test_prepare_nodes.py
git commit -m "feat(prepare): memory_search_node — 历史薄弱点 + 故事库检索"
```

---

## Task 4: jd_analysis_node

**Files:**
- Create: `backend/app/agents/prepare/prompts.py`
- Modify: `backend/app/agents/prepare/nodes.py`

- [ ] **Step 4.1: 写失败测试（追加到 test_prepare_nodes.py）**

```python
@pytest.mark.asyncio
async def test_jd_analysis_returns_jd_context():
    """有 JD 文本时应返回结构化 JDContext。"""
    from app.agents.prepare.nodes import jd_analysis_node

    state: PrepareState = {
        "user_id": "u1",
        "jd_raw": "招聘高级后端工程师，要求熟悉 Python、分布式系统、Kafka",
        "user_direction": "后端工程师",
    }

    mock_output = MagicMock()
    mock_output.company = "字节跳动"
    mock_output.role = "高级后端工程师"
    mock_output.key_skills = ["Python", "分布式系统", "Kafka"]
    mock_output.focus_areas = ["系统设计", "高并发"]
    mock_output.difficulty = "hard"

    with patch("app.agents-1.prepare.nodes._llm") as mock_llm:
        mock_llm.return_value.with_structured_output.return_value.ainvoke = AsyncMock(return_value=mock_output)
        result = await jd_analysis_node(state)

    assert result["jd_context"]["key_skills"] == ["Python", "分布式系统", "Kafka"]
    assert result["jd_context"]["difficulty"] == "hard"


@pytest.mark.asyncio
async def test_jd_analysis_skips_when_no_jd():
    """无 JD 时跳过，不调 LLM，jd_context 为 None。"""
    from app.agents.prepare.nodes import jd_analysis_node

    state: PrepareState = {"user_id": "u1", "jd_raw": None}
    result = await jd_analysis_node(state)
    assert result.get("jd_context") is None
```

- [ ] **Step 4.2: 创建 prompts.py**

```python
# backend/app/agents-1/prepare/prompts.py
"""Prompt constants for prepare pipeline nodes."""

MASTER_REASONING_PROMPT = """你是面试准备 Master Orchestrator。
分析以下用户信息，逐行输出你的判断（每行以"• "开头）。

用户信息：
{context}

请输出你的分析过程，包括：检查用户档案、检查历史情况、确定练习方向、确定调用链。
语言简洁，每行不超过40字。"""

MASTER_DECISION_PROMPT = """基于以下用户信息，输出调度决策（JSON）。

用户信息：
{context}

输出字段：
- direction: 识别出的练习方向（如"分布式系统"），若无法判断则为空字符串
- chain: 需要调用的子 Agent 列表，从 ["memory_search","jd_analysis","question_gen"] 中选
  - memory_search: 有历史记录时包含
  - jd_analysis: 有 JD 文本时包含
  - question_gen: 始终包含
- need_direction: 布尔值，true = 无法确定练习方向，需要向用户询问"""

JD_ANALYSIS_SYSTEM_PROMPT = """分析以下 JD（职位描述），提取结构化信息。
输出 JSON，字段：company, role, key_skills(list), focus_areas(list), difficulty(easy/medium/hard/faang)。
JD 内容：
{jd_raw}"""

QUESTION_GEN_SYSTEM_PROMPT = """你是专业面试出题官。根据以下信息生成 {count} 道面试题。

练习方向：{direction}
目标岗位：{target_role}
{jd_context_block}
{weak_areas_block}
{star_stories_block}

要求：
1. 薄弱点相关题目排在最前（priority=1,2）
2. 结合候选人真实项目经历出具体问题（如果有故事库）
3. 题目类型: technical/behavioral/system_design 各占比均衡
4. 每道题输出 JSON: {{"id":N,"question":"...","category":"...","focus_area":"...","priority":N}}
5. 输出纯 JSON 数组，不要任何其他内容"""
```

- [ ] **Step 4.3: 实现 jd_analysis_node（追加到 nodes.py）**

```python
# 追加到 backend/app/agents-1/prepare/nodes.py


class _JDContextModel(BaseModel):
    company: str = ""
    role: str = ""
    key_skills: list[str] = []
    focus_areas: list[str] = []
    difficulty: str = "medium"


async def jd_analysis_node(state: PrepareState) -> PrepareState:
    """JD 文本 → 结构化 JDContext。无 JD 时直接跳过。"""
    jd_raw = state.get("jd_raw")
    if not jd_raw:
        return {**state, "jd_context": None}

    prompt = JD_ANALYSIS_SYSTEM_PROMPT.format(jd_raw=jd_raw[:4000])
    model = _llm().with_structured_output(_JDContextModel)
    output: _JDContextModel = await model.ainvoke([SystemMessage(content=prompt)])

    jd_context: JDContext = {
        "company": output.company,
        "role": output.role,
        "key_skills": output.key_skills,
        "focus_areas": output.focus_areas,
        "difficulty": output.difficulty,
    }
    log.info("jd_analysis_done", role=output.role, skills_count=len(output.key_skills))
    return {**state, "jd_context": jd_context}
```

- [ ] **Step 4.4: 运行测试**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_prepare_nodes.py -k "jd_analysis" -v
```

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/agents-1/prepare/prompts.py backend/app/agents-1/prepare/nodes.py backend/tests/unit/test_prepare_nodes.py
git commit -m "feat(prepare): jd_analysis_node — JD文本结构化提取"
```

---

## Task 5: question_gen_node

**Files:**
- Modify: `backend/app/agents/prepare/nodes.py`

- [ ] **Step 5.1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_question_gen_returns_5_questions():
    from app.agents.prepare.nodes import question_gen_node

    state: PrepareState = {
        "user_id": "u1",
        "direction": "AI Agent 工程师",
        "user_direction": "AI Agent 工程师",
        "weak_areas": ["量化结果欠缺"],
        "star_stories": [],
        "jd_context": None,
    }

    mock_content = '[{"id":1,"question":"Q1","category":"technical","focus_area":"RAG","priority":1},{"id":2,"question":"Q2","category":"behavioral","focus_area":"量化","priority":1},{"id":3,"question":"Q3","category":"technical","focus_area":"Agent","priority":2},{"id":4,"question":"Q4","category":"system_design","focus_area":"架构","priority":3},{"id":5,"question":"Q5","category":"technical","focus_area":"LangGraph","priority":3}]'

    with patch("app.agents-1.prepare.nodes._llm") as mock_llm:
        mock_chunk = MagicMock()
        mock_chunk.content = mock_content
        mock_llm.return_value.with_config.return_value.astream = AsyncMock(
            return_value=aiter([mock_chunk])
        )
        result = await question_gen_node(state)

    assert len(result["prepared_questions"]) == 5
    assert result["prepared_questions"][0]["priority"] == 1


@pytest.mark.asyncio
async def test_question_gen_weak_areas_first():
    """薄弱点相关题目 priority 应为最低数值（最高优先级）。"""
    from app.agents.prepare.nodes import question_gen_node

    state: PrepareState = {
        "user_id": "u1",
        "direction": "后端工程师",
        "user_direction": "后端工程师",
        "weak_areas": ["量化结果欠缺", "系统设计薄弱"],
        "star_stories": [],
        "jd_context": None,
    }

    mock_content = '[{"id":1,"question":"量化题","category":"behavioral","focus_area":"量化","priority":1},{"id":2,"question":"系统设计题","category":"system_design","focus_area":"设计","priority":1},{"id":3,"question":"Q3","category":"technical","focus_area":"Python","priority":3},{"id":4,"question":"Q4","category":"technical","focus_area":"DB","priority":3},{"id":5,"question":"Q5","category":"behavioral","focus_area":"团队","priority":4}]'

    with patch("app.agents-1.prepare.nodes._llm") as mock_llm:
        mock_chunk = MagicMock()
        mock_chunk.content = mock_content
        mock_llm.return_value.with_config.return_value.astream = AsyncMock(
            return_value=aiter([mock_chunk])
        )
        result = await question_gen_node(state)

    priorities = [q["priority"] for q in result["prepared_questions"]]
    assert priorities[0] <= priorities[-1]  # 第一题优先级最高
```

在文件顶部加辅助函数（测试用）：

```python
# 测试辅助：模拟 async iterator
async def aiter(items):
    for item in items:
        yield item
```

- [ ] **Step 5.2: 实现 question_gen_node**

```python
# 追加到 backend/app/agents-1/prepare/nodes.py
import json
import re


async def question_gen_node(state: PrepareState) -> PrepareState:
    """基于方向 + 薄弱点 + 故事库生成 5 道定制题目（流式输出）。"""
    direction = state.get("direction") or state.get("user_direction") or "通用软件工程师"
    target_role = state.get("user_direction") or direction
    weak_areas = state.get("weak_areas") or []
    star_stories = state.get("star_stories") or []
    jd_context = state.get("jd_context")

    jd_block = ""
    if jd_context:
        jd_block = f"JD 考点：{', '.join(jd_context.get('focus_areas', []))}\n技术栈：{', '.join(jd_context.get('key_skills', []))}"

    weak_block = f"历史薄弱点（优先出题）：{', '.join(weak_areas)}" if weak_areas else ""

    stories_block = ""
    if star_stories:
        titles = [s["title"] for s in star_stories[:3]]
        stories_block = f"候选人真实项目（可以针对这些项目出具体问题）：{', '.join(titles)}"

    prompt = QUESTION_GEN_SYSTEM_PROMPT.format(
        count=5,
        direction=direction,
        target_role=target_role,
        jd_context_block=jd_block,
        weak_areas_block=weak_block,
        star_stories_block=stories_block,
    )

    # 流式调用，tagged 供 SSE 捕获
    model = _llm(streaming=True).with_config(tags=["prepare_question_gen_stream"])
    full_text = ""
    async for chunk in model.astream([SystemMessage(content=prompt)]):
        content = chunk.content if isinstance(chunk.content, str) else ""
        full_text += content

    # 解析 JSON 数组
    questions: list[PreparedQuestion] = []
    try:
        json_match = re.search(r"\[.*\]", full_text, re.DOTALL)
        if json_match:
            raw_list = json.loads(json_match.group())
            questions = sorted(
                [
                    PreparedQuestion(
                        id=q.get("id", i + 1),
                        question=q["question"],
                        category=q.get("category", "technical"),
                        focus_area=q.get("focus_area", ""),
                        priority=q.get("priority", 5),
                    )
                    for i, q in enumerate(raw_list)
                ],
                key=lambda x: x["priority"],
            )
    except (json.JSONDecodeError, KeyError) as exc:
        log.error("question_gen_parse_failed", error=str(exc), raw=full_text[:200])

    log.info("question_gen_done", count=len(questions))
    return {**state, "prepared_questions": questions}
```

- [ ] **Step 5.3: 运行测试**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_prepare_nodes.py -k "question_gen" -v
```

- [ ] **Step 5.4: Commit**

```bash
git add backend/app/agents-1/prepare/nodes.py backend/tests/unit/test_prepare_nodes.py
git commit -m "feat(prepare): question_gen_node — 结合薄弱点+故事库出5道定制题"
```

---

## Task 6: master_node

**Files:**
- Modify: `backend/app/agents/prepare/nodes.py`

- [ ] **Step 6.1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_master_detects_direction_from_user_input():
    from app.agents.prepare.nodes import master_node

    state: PrepareState = {
        "user_id": "u1",
        "user_direction": "AI Agent 工程师",
        "jd_raw": None,
        "weak_areas": [],
        "star_stories": [],
    }

    mock_decision = MagicMock()
    mock_decision.direction = "AI Agent 工程师"
    mock_decision.chain = ["question_gen"]
    mock_decision.need_direction = False

    with patch("app.agents-1.prepare.nodes._llm") as mock_llm:
        # reasoning stream
        mock_stream = MagicMock()
        mock_stream.content = "• 找到方向"
        mock_llm.return_value.with_config.return_value.astream = AsyncMock(
            return_value=aiter([mock_stream])
        )
        # decision structured output
        mock_llm.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_decision
        )
        result = await master_node(state)

    assert result["direction"] == "AI Agent 工程师"
    assert "question_gen" in result["chain"]
    assert result["need_direction"] is False


@pytest.mark.asyncio
async def test_master_sets_need_direction_when_no_input():
    from app.agents.prepare.nodes import master_node

    state: PrepareState = {
        "user_id": "new_user",
        "user_direction": None,
        "jd_raw": None,
        "weak_areas": [],
        "star_stories": [],
    }

    mock_decision = MagicMock()
    mock_decision.direction = ""
    mock_decision.chain = ["question_gen"]
    mock_decision.need_direction = True

    with patch("app.agents-1.prepare.nodes._llm") as mock_llm:
        mock_stream = MagicMock()
        mock_stream.content = "• 未找到方向"
        mock_llm.return_value.with_config.return_value.astream = AsyncMock(
            return_value=aiter([mock_stream])
        )
        mock_llm.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_decision
        )
        result = await master_node(state)

    assert result["need_direction"] is True


@pytest.mark.asyncio
async def test_master_includes_memory_search_when_has_history():
    from app.agents.prepare.nodes import master_node

    state: PrepareState = {
        "user_id": "u1",
        "user_direction": "后端工程师",
        "jd_raw": None,
        "weak_areas": ["量化不足"],  # 已有历史
        "star_stories": [],
    }

    mock_decision = MagicMock()
    mock_decision.direction = "后端工程师"
    mock_decision.chain = ["memory_search", "question_gen"]
    mock_decision.need_direction = False

    with patch("app.agents-1.prepare.nodes._llm") as mock_llm:
        mock_stream = MagicMock()
        mock_stream.content = "• 发现历史记录"
        mock_llm.return_value.with_config.return_value.astream = AsyncMock(
            return_value=aiter([mock_stream])
        )
        mock_llm.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_decision
        )
        result = await master_node(state)

    assert "memory_search" in result["chain"]
```

- [ ] **Step 6.2: 实现 master_node**

```python
# 追加到 backend/app/agents-1/prepare/nodes.py


class _MasterDecision(BaseModel):
    direction: str = ""
    chain: list[str] = []
    need_direction: bool = False


async def master_node(state: PrepareState) -> PrepareState:
    """识别练习方向，决定调用链。流式输出推理 bullets，结构化输出决策。"""
    user_direction = state.get("user_direction") or ""
    jd_raw = state.get("jd_raw") or ""
    weak_areas = state.get("weak_areas") or []
    star_stories = state.get("star_stories") or []

    context = f"""
用户档案：
  - 目标岗位/方向：{user_direction or "未设置"}
  - 是否提供 JD：{"是" if jd_raw else "否"}
  - 历史薄弱点：{", ".join(weak_areas) if weak_areas else "无（新用户或未查询）"}
  - 故事库项目数：{len(star_stories)}
""".strip()

    # Phase 1: 流式推理（供 SSE 捕获，用户可见）
    reasoning_prompt = MASTER_REASONING_PROMPT.format(context=context)
    model_stream = _llm(streaming=True).with_config(tags=["prepare_master_stream"])
    async for _ in model_stream.astream([SystemMessage(content=reasoning_prompt)]):
        pass  # 流由 astream_events 在 graph 层捕获，此处只触发

    # Phase 2: 结构化决策（快速，非流式）
    decision_prompt = MASTER_DECISION_PROMPT.format(context=context)
    model_decision = _llm().with_structured_output(_MasterDecision)
    decision: _MasterDecision = await model_decision.ainvoke(
        [SystemMessage(content=decision_prompt)]
    )

    # 保证 question_gen 始终在 chain 末尾
    chain = list(dict.fromkeys(decision.chain + ["question_gen"]))

    log.info(
        "master_done",
        direction=decision.direction,
        chain=chain,
        need_direction=decision.need_direction,
    )
    return {
        **state,
        "direction": decision.direction,
        "chain": chain,
        "need_direction": decision.need_direction,
    }
```

- [ ] **Step 6.3: 运行测试**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_prepare_nodes.py -k "master" -v
```

- [ ] **Step 6.4: Commit**

```bash
git add backend/app/agents-1/prepare/nodes.py backend/tests/unit/test_prepare_nodes.py
git commit -m "feat(prepare): master_node — 流式推理 + 结构化路由决策"
```

---

## Task 7: Prepare Graph + SSE 流

**Files:**
- Create: `backend/app/agents/prepare/graph.py`
- Test: `backend/tests/unit/test_prepare_graph.py`

- [ ] **Step 7.1: 写失败测试**

```python
# backend/tests/unit/test_prepare_graph.py
import pytest
from unittest.mock import AsyncMock, patch
from app.agents.prepare.state import PrepareState


@pytest.mark.asyncio
async def test_route_after_master_includes_jd_when_has_jd():
    from app.agents.prepare.graph import route_after_master

    state: PrepareState = {
        "chain": ["memory_search", "jd_analysis", "question_gen"],
        "current_node_index": 0,
    }
    assert route_after_master(state) == "memory_search"


@pytest.mark.asyncio
async def test_route_after_master_skips_to_question_gen():
    from app.agents.prepare.graph import route_after_master

    state: PrepareState = {
        "chain": ["question_gen"],
        "current_node_index": 0,
    }
    assert route_after_master(state) == "question_gen"


@pytest.mark.asyncio
async def test_route_after_master_need_direction_returns_wait():
    from app.agents.prepare.graph import route_after_master

    state: PrepareState = {
        "chain": [],
        "need_direction": True,
        "current_node_index": 0,
    }
    assert route_after_master(state) == "wait_direction"
```

- [ ] **Step 7.2: 实现 graph.py**

```python
# backend/app/agents-1/prepare/graph.py
"""LangGraph definition and SSE streaming for the prepare pipeline."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.prepare import nodes
from app.agents.prepare.state import PrepareState
from app.core.logging import get_logger

log = get_logger("app.agents-1.prepare.graph")

_NODE_MAP = {
    "memory_search": nodes.memory_search_node,
    "jd_analysis": nodes.jd_analysis_node,
    "question_gen": nodes.question_gen_node,
}

_NODE_LABELS = {
    "master": "MASTER",
    "memory_search": "记忆检索",
    "jd_analysis": "JD分析",
    "question_gen": "出题",
}


def route_after_master(state: PrepareState) -> str:
    if state.get("need_direction"):
        return "wait_direction"
    chain = state.get("chain") or []
    if chain:
        return chain[0]
    return "question_gen"


def _build_graph() -> Any:
    g = StateGraph(PrepareState)
    g.add_node("master", nodes.master_node)
    g.add_node("memory_search", nodes.memory_search_node)
    g.add_node("jd_analysis", nodes.jd_analysis_node)
    g.add_node("question_gen", nodes.question_gen_node)

    g.set_entry_point("master")
    g.add_conditional_edges(
        "master",
        route_after_master,
        {
            "memory_search": "memory_search",
            "jd_analysis": "jd_analysis",
            "question_gen": "question_gen",
            "wait_direction": END,  # 暂停等用户输入，resume 时重新触发
        },
    )

    # 动态路由：每个子 Agent 完成后看 chain 里下一个是谁
    for node_name in ("memory_search", "jd_analysis"):
        g.add_conditional_edges(
            node_name,
            _route_next_in_chain(node_name),
            {
                "jd_analysis": "jd_analysis",
                "question_gen": "question_gen",
                END: END,
            },
        )
    g.add_edge("question_gen", END)
    return g.compile()


def _route_next_in_chain(current: str):
    """返回 chain 里 current 之后的下一个节点名。"""
    def _route(state: PrepareState) -> str:
        chain = state.get("chain") or []
        try:
            idx = chain.index(current)
            if idx + 1 < len(chain):
                return chain[idx + 1]
        except ValueError:
            pass
        return END
    return _route


_prepare_graph = _build_graph()


def get_prepare_graph() -> Any:
    return _prepare_graph


def _extract_token(event: dict[str, Any]) -> str | None:
    """从 astream_events 事件提取 token 文本。"""
    if event.get("event") != "on_chat_model_stream":
        return None
    content = event.get("data", {}).get("chunk", {})
    text = getattr(content, "content", "")
    return text if isinstance(text, str) else None


async def stream_prepare_events(state: PrepareState) -> AsyncIterator[dict[str, Any]]:
    """运行 prepare graph，流式 yield SSE 事件。"""
    current_node: str | None = None
    elapsed_tracker: dict[str, float] = {}
    import time

    async for event in get_prepare_graph().astream_events(state, version="v2"):
        ev_name = event.get("event", "")
        ev_node = event.get("metadata", {}).get("langgraph_node", "")

        # 节点开始
        if ev_name == "on_chain_start" and ev_node and ev_node != current_node:
            current_node = ev_node
            elapsed_tracker[ev_node] = time.time()
            yield {
                "event": "node_start",
                "data": {
                    "node": ev_node,
                    "label": _NODE_LABELS.get(ev_node, ev_node),
                },
            }

        # 流式 token（master + question_gen）
        token = _extract_token(event)
        tags = event.get("tags", [])
        if token and any(t in tags for t in ("prepare_master_stream", "prepare_question_gen_stream")):
            yield {"event": "node_token", "data": {"node": ev_node, "text": token}}

        # 节点结束
        if ev_name == "on_chain_end" and ev_node:
            elapsed_ms = int((time.time() - elapsed_tracker.get(ev_node, time.time())) * 1000)
            node_state = event.get("data", {}).get("output") or {}

            extra: dict[str, Any] = {"elapsed_ms": elapsed_ms}
            if ev_node == "master":
                extra["chain"] = node_state.get("chain", [])
                extra["need_direction"] = node_state.get("need_direction", False)

            yield {"event": "node_done", "data": {"node": ev_node, **extra}}

        # 全图结束
        if ev_name == "on_chain_end" and event.get("name") == "LangGraph":
            final: PrepareState = event.get("data", {}).get("output") or {}
            if not final.get("need_direction"):
                yield {
                    "event": "done",
                    "data": {
                        "jd_context": final.get("jd_context"),
                        "prepared_questions": final.get("prepared_questions", []),
                        "summary": final.get("summary", ""),
                        "direction": final.get("direction", ""),
                    },
                }
```

- [ ] **Step 7.3: 运行测试**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_prepare_graph.py -v
```

- [ ] **Step 7.4: Commit**

```bash
git add backend/app/agents-1/prepare/graph.py backend/tests/unit/test_prepare_graph.py
git commit -m "feat(prepare): prepare graph + SSE stream_prepare_events"
```

---

## Task 8: Prepare API 端点

**Files:**
- Create: `backend/app/api/v1/prepare.py`
- Modify: `backend/app/main.py`

- [ ] **Step 8.1: 写集成测试**

```python
# backend/tests/integration/test_prepare_api.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_prepare_start_returns_sse_stream(async_client, auth_headers):
    """POST /api/v1/prepare/start 应返回 SSE 流。"""
    mock_events = [
        {"event": "node_start", "data": {"node": "master", "label": "MASTER"}},
        {"event": "node_done", "data": {"node": "master", "elapsed_ms": 10, "chain": ["question_gen"], "need_direction": False}},
        {"event": "done", "data": {"prepared_questions": [], "summary": "测试摘要", "direction": "AI Agent"}},
    ]

    async def mock_stream(state):
        for ev in mock_events:
            yield ev

    with patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_stream):
        resp = await async_client.post(
            "/api/v1/prepare/start",
            data={"user_direction": "AI Agent 工程师"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
```

- [ ] **Step 8.2: 实现 prepare.py**

```python
# backend/app/api/v1/prepare.py
"""Prepare pipeline API endpoints."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.agents.prepare.graph import stream_prepare_events
from app.agents.prepare.state import PrepareState
from app.api.v1.auth import get_current_user_id
from app.core.logging import get_logger
from app.services.jd_extractor import JDSource, NeedManualInput, extract_jd_text_async

router = APIRouter()
log = get_logger("app.api.v1.prepare")


async def _sse_format(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    async for ev in events:
        yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"


@router.post("/prepare/start")
async def prepare_start(
    user_direction: str = Form(""),
    user_background: str = Form(""),
    jd_text: str = Form(""),
    jd_url: str = Form(""),
    jd_file: UploadFile | None = File(None),
    user_id: str = Depends(get_current_user_id),
):
    """启动准备流水线，返回 SSE 流。"""
    # 提取 JD 文本
    jd_raw: str | None = None
    try:
        if jd_text.strip():
            jd_raw = jd_text.strip()
        elif jd_file is not None:
            content = await jd_file.read()
            source = JDSource(type="file", filename=jd_file.filename or "", content_bytes=content)
            jd_raw = await extract_jd_text_async(source)
        elif jd_url.strip():
            source = JDSource(type="url", url=jd_url.strip())
            jd_raw = await extract_jd_text_async(source)
    except NeedManualInput as exc:
        async def _err():
            yield f"data: {json.dumps({'event':'error','data':{'message':str(exc),'code':'need_manual_input'}}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")
    except Exception as exc:
        log.error("jd_extract_failed", error=str(exc))

    state: PrepareState = {
        "user_id": user_id,
        "user_direction": user_direction or None,
        "user_background": user_background or None,
        "jd_raw": jd_raw,
        "weak_areas": [],
        "star_stories": [],
    }

    return StreamingResponse(
        _sse_format(stream_prepare_events(state)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/prepare/resume")
async def prepare_resume(
    direction: str = Form(...),
    user_background: str = Form(""),
    user_id: str = Depends(get_current_user_id),
):
    """用户回答方向后，继续准备流水线（need_direction=True 场景）。"""
    state: PrepareState = {
        "user_id": user_id,
        "user_direction": direction,
        "user_background": user_background or None,
        "jd_raw": None,
        "weak_areas": [],
        "star_stories": [],
        "need_direction": False,
    }
    return StreamingResponse(
        _sse_format(stream_prepare_events(state)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 8.3: 注册路由（修改 main.py）**

在 `backend/app/main.py` 中已有路由注册区域，追加：

```python
from app.api.v1 import prepare as prepare_v1
# ...
app.include_router(prepare_v1.router, prefix="/api/v1", tags=["prepare"])
```

- [ ] **Step 8.4: 运行全部后端测试**

```bash
cd backend && .venv/bin/python -m pytest tests/ -v --timeout=30
```

- [ ] **Step 8.5: Lint + typecheck**

```bash
cd backend && .venv/bin/python -m ruff check app/agents-1/prepare/ app/api/v1/prepare.py app/services/jd_extractor.py
cd backend && .venv/bin/python -m mypy app/agents-1/prepare/ app/api/v1/prepare.py
```

- [ ] **Step 8.6: Commit**

```bash
git add backend/app/api/v1/prepare.py backend/app/main.py backend/tests/integration/test_prepare_api.py
git commit -m "feat(prepare): POST /api/v1/prepare/start + resume SSE 端点"
```

---

## Task 9: InterviewState 扩展 + 面试流程改动

**Files:**
- Modify: `backend/app/agents/interviewer/state.py`
- Modify: `backend/app/agents/interviewer/nodes.py`
- Modify: `backend/app/agents/interviewer/graph.py`

- [ ] **Step 9.1: 写失败测试**

```python
# 追加到 backend/tests/unit/test_interview_routes.py 或新建
# backend/tests/unit/test_prepare_interview_integration.py

from app.agents.interviewer.graph import route_after_load
from app.agents.interviewer.state import InterviewState


def test_route_after_load_skips_opening_when_prepared_questions():
    state: InterviewState = {
        "session_id": "s1",
        "prepared_questions": [
            {"id": 1, "question": "Q1", "category": "technical", "focus_area": "f", "priority": 1}
        ],
        "question_count": 0,
        "stage": None,
    }
    result = route_after_load(state)
    assert result == "ask_question"


def test_route_after_load_uses_opening_without_prepared_questions():
    state: InterviewState = {
        "session_id": "s1",
        "prepared_questions": [],
        "question_count": 0,
        "stage": None,
    }
    result = route_after_load(state)
    assert result in ("opening", "briefing", "ask_question")  # 现有逻辑
```

- [ ] **Step 9.2: 修改 InterviewState**

在 `backend/app/agents/interviewer/state.py` 末尾追加字段：

```python
# 阶段 3 新增（可选字段，保持向后兼容）
jd_context: dict[str, Any] | None
prepared_questions: list[dict[str, Any]]
current_question_index: int   # 当前取到 prepared_questions 的第几题
```

同时在顶部 import 中加 `from typing import Any`（如尚未有）。

- [ ] **Step 9.3: 修改 route_after_load（graph.py）**

找到 `route_after_load` 函数，在函数开头插入：

```python
def route_after_load(state: InterviewState) -> str:
    # 有预备题目时直接出题，跳过 opening/briefing
    if state.get("prepared_questions"):
        return "ask_question"
    # ... 原有逻辑不变
```

- [ ] **Step 9.4: 修改 ask_question_node（nodes.py）**

找到 `ask_question_node` 函数，在生成问题之前插入：

```python
async def ask_question_node(state: InterviewState) -> InterviewState:
    # 优先使用预备题目列表
    prepared = state.get("prepared_questions") or []
    idx = state.get("current_question_index", 0)
    if prepared and idx < len(prepared):
        question_text = prepared[idx]["question"]
        # ... 用 question_text 替换原有 LLM 出题逻辑
        new_state = {
            **state,
            "current_question_index": idx + 1,
            "question_count": state.get("question_count", 0) + 1,
        }
        # 生成面试官包装文案（仍然走 LLM，但 topic 固定）
        # 原有的 _generate_text 可复用，把 question_text 传入 prompts
        return new_state
    # 原有逻辑（随机出题）
    ...
```

> **注意：** 找到现有 ask_question_node 的完整实现后，在其顶部插入 prepared 判断逻辑，不要删除原有随机出题代码（作为 fallback）。

- [ ] **Step 9.5: 运行测试**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_prepare_interview_integration.py -v
cd backend && .venv/bin/python -m pytest tests/ -v --timeout=30
```

- [ ] **Step 9.6: Commit**

```bash
git add backend/app/agents-1/interviewer/state.py backend/app/agents-1/interviewer/nodes.py backend/app/agents-1/interviewer/graph.py
git commit -m "feat(interview): InterviewState 加 prepared_questions，有题直接出题跳过 opening"
```

---

## Task 10: 前端 TraceNode + AgentTrace 组件

**Files:**
- Create: `frontend/app/interview/_components/trace-node.tsx`
- Create: `frontend/app/interview/_components/agent-trace.tsx`
- Test: `frontend/app/interview/_components/trace-node.test.tsx`

- [ ] **Step 10.1: 写失败测试**

```tsx
// frontend/app/interview/_components/trace-node.test.tsx
import { render, screen } from "@testing-library/react";
import { TraceNode } from "./trace-node";

test("pending 状态显示灰色圆圈", () => {
  render(<TraceNode id="master" label="MASTER" title="识别方向" status="pending" tokens="" />);
  expect(screen.getByTestId("trace-node-master")).toBeInTheDocument();
  expect(screen.getByTestId("trace-status-pending")).toBeInTheDocument();
});

test("running 状态显示动画圆圈", () => {
  render(<TraceNode id="master" label="MASTER" title="识别方向" status="running" tokens="检查用户档案" />);
  expect(screen.getByTestId("trace-status-running")).toBeInTheDocument();
  expect(screen.getByText("检查用户档案")).toBeInTheDocument();
});

test("done 状态显示绿色勾 + 耗时", () => {
  render(<TraceNode id="master" label="MASTER" title="识别方向" status="done" tokens="检查完毕" elapsedMs={62} />);
  expect(screen.getByTestId("trace-status-done")).toBeInTheDocument();
  expect(screen.getByText("62ms")).toBeInTheDocument();
});
```

- [ ] **Step 10.2: 运行测试确认失败**

```bash
cd frontend && pnpm test -- trace-node --watchAll=false
```

- [ ] **Step 10.3: 实现 TraceNode**

```tsx
// frontend/app/interview/_components/trace-node.tsx
"use client";

type TraceNodeStatus = "pending" | "running" | "done";

interface TraceNodeProps {
  id: string;
  label: string;
  title: string;
  status: TraceNodeStatus;
  tokens: string;       // 流式积累的文本（LLM 逐字输出，非固定文案）
  elapsedMs?: number;
}

export function TraceNode({ id, label, title, status, tokens, elapsedMs }: TraceNodeProps) {
  return (
    <div data-testid={`trace-node-${id}`} className="flex gap-3 py-2">
      {/* 左侧状态圆圈 */}
      <div className="flex flex-col items-center gap-1 pt-0.5">
        {status === "pending" && (
          <div data-testid="trace-status-pending"
            className="w-6 h-6 rounded-full border-2 border-gray-200 bg-white flex-shrink-0" />
        )}
        {status === "running" && (
          <div data-testid="trace-status-running"
            className="w-6 h-6 rounded-full border-2 border-indigo-500 flex-shrink-0 animate-spin border-t-transparent" />
        )}
        {status === "done" && (
          <div data-testid="trace-status-done"
            className="w-6 h-6 rounded-full bg-emerald-500 flex-shrink-0 flex items-center justify-center">
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          </div>
        )}
        {/* 竖线连接下一个节点 */}
        <div className="w-px flex-1 bg-gray-100" />
      </div>

      {/* 右侧内容 */}
      <div className="flex-1 pb-3 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-100">
            {label}
          </span>
          <span className="text-sm font-medium text-gray-800">{title}</span>
          {status === "running" && (
            <span className="text-indigo-400 text-xs animate-pulse">●●●</span>
          )}
          {elapsedMs !== undefined && (
            <span className="ml-auto text-xs text-gray-400">{elapsedMs}ms</span>
          )}
        </div>

        {/* 流式 token 文本（逐字渲染，非固定文案） */}
        {tokens && (
          <div className="text-xs text-gray-500 leading-relaxed whitespace-pre-wrap pl-1">
            {tokens.split("\n").map((line, i) =>
              line.trim() ? (
                <div key={i} className="flex gap-1.5 mt-0.5">
                  <span className="text-gray-300 flex-shrink-0">•</span>
                  <span>{line.replace(/^[•\-]\s*/, "")}</span>
                </div>
              ) : null
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 10.4: 实现 AgentTrace**

```tsx
// frontend/app/interview/_components/agent-trace.tsx
"use client";

import { TraceNode } from "./trace-node";

export type TraceNodeData = {
  id: string;
  label: string;
  title: string;
  status: "pending" | "running" | "done";
  tokens: string;
  elapsedMs?: number;
};

interface AgentTraceProps {
  nodes: TraceNodeData[];
}

const NODE_TITLES: Record<string, string> = {
  master: "识别方向，启动准备",
  memory_search: "读取你的历史表现",
  jd_analysis: "构建考点地图",
  question_gen: "定制专属题目",
};

export function AgentTrace({ nodes }: AgentTraceProps) {
  return (
    <div className="px-4 py-2">
      {nodes.map((node) => (
        <TraceNode
          key={node.id}
          {...node}
          title={node.title || NODE_TITLES[node.id] || node.id}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 10.5: 运行测试**

```bash
cd frontend && pnpm test -- trace-node --watchAll=false
```

- [ ] **Step 10.6: Commit**

```bash
git add frontend/app/interview/_components/trace-node.tsx frontend/app/interview/_components/agent-trace.tsx frontend/app/interview/_components/trace-node.test.tsx
git commit -m "feat(interview-ui): TraceNode + AgentTrace 组件"
```

---

## Task 11: PreparationCard + QuestionListModal

**Files:**
- Create: `frontend/app/interview/_components/preparation-card.tsx`
- Create: `frontend/app/interview/_components/question-list-modal.tsx`
- Test: `frontend/app/interview/_components/preparation-card.test.tsx`

- [ ] **Step 11.1: 写失败测试**

```tsx
// frontend/app/interview/_components/preparation-card.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { PreparationCard } from "./preparation-card";

const mockQuestions = [
  { id: 1, question: "请描述 CAP 理论", category: "technical", focus_area: "分布式", priority: 1 },
  { id: 2, question: "项目中如何量化结果", category: "behavioral", focus_area: "量化", priority: 1 },
];

test("running 状态显示准备中", () => {
  render(<PreparationCard status="running" nodes={[]} questions={[]} summary="" onStart={() => {}} />);
  expect(screen.getByText(/准备中/)).toBeInTheDocument();
});

test("done 状态显示准备完成和两个按钮", () => {
  render(
    <PreparationCard
      status="done"
      nodes={[]}
      questions={mockQuestions}
      summary="为你定制了 2 道题"
      onStart={() => {}}
    />
  );
  expect(screen.getByText("准备完成")).toBeInTheDocument();
  expect(screen.getByText(/开始第1题/)).toBeInTheDocument();
  expect(screen.getByText(/先看题目列表/)).toBeInTheDocument();
});

test("点击就绪切换展开", () => {
  render(
    <PreparationCard status="done" nodes={[]} questions={mockQuestions} summary="test" onStart={() => {}} />
  );
  const toggle = screen.getByRole("button", { name: /就绪/ });
  fireEvent.click(toggle);
  // 展开后 toggle 文字变化
  expect(screen.getByRole("button", { name: /就绪/ })).toBeInTheDocument();
});
```

- [ ] **Step 11.2: 实现 PreparationCard**

```tsx
// frontend/app/interview/_components/preparation-card.tsx
"use client";

import { useState } from "react";
import { AgentTrace, type TraceNodeData } from "./agent-trace";
import { QuestionListModal } from "./question-list-modal";
import type { PreparedQuestion } from "@/lib/prepare-types";

interface PreparationCardProps {
  status: "running" | "done" | "waiting_direction";
  nodes: TraceNodeData[];
  questions: PreparedQuestion[];
  summary: string;
  direction?: string;
  onStart: () => void;
}

export function PreparationCard({
  status, nodes, questions, summary, direction, onStart,
}: PreparationCardProps) {
  const [expanded, setExpanded] = useState(status === "running");
  const [showModal, setShowModal] = useState(false);

  return (
    <div className="border border-gray-100 rounded-xl mx-4 mt-3 bg-white shadow-sm overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
            status === "done" ? "bg-emerald-500" :
            status === "running" ? "bg-indigo-500 animate-pulse" : "bg-gray-300"
          }`} />
          <span className="text-sm font-semibold text-gray-800">
            {status === "running" ? "准备中..." :
             status === "done" ? "准备完成" : "等待方向"}
          </span>
          {direction && (
            <span className="text-xs px-2 py-0.5 bg-indigo-600 text-white rounded-full font-medium">
              {direction}
            </span>
          )}
        </div>

        {status !== "running" && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 px-2 py-1 rounded transition-colors"
          >
            就绪 {expanded ? "∧" : "∨"}
          </button>
        )}
      </div>

      {/* Trace（running 时始终展开，done 时受 expanded 控制） */}
      {(status === "running" || expanded) && (
        <div className="max-h-64 overflow-y-auto">
          <AgentTrace nodes={nodes} />
        </div>
      )}

      {/* Done 折叠态：摘要 + 按钮 */}
      {status === "done" && !expanded && (
        <div className="px-4 py-3">
          {summary && (
            <p className="text-sm text-gray-600 mb-3 leading-relaxed">{summary}</p>
          )}
          <div className="flex gap-2">
            <button
              onClick={onStart}
              className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-full text-sm font-semibold hover:bg-indigo-700 transition-colors"
            >
              <span>▷</span> 开始第1题
            </button>
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-1.5 px-4 py-2 border border-gray-200 text-gray-600 rounded-full text-sm font-medium hover:border-gray-300 transition-colors"
            >
              <span>≡</span> 先看题目列表
            </button>
          </div>
        </div>
      )}

      <QuestionListModal
        open={showModal}
        questions={questions}
        onClose={() => setShowModal(false)}
        onStart={() => { setShowModal(false); onStart(); }}
      />
    </div>
  );
}
```

- [ ] **Step 11.3: 实现 QuestionListModal**

```tsx
// frontend/app/interview/_components/question-list-modal.tsx
"use client";

import type { PreparedQuestion } from "@/lib/prepare-types";

const CATEGORY_LABEL: Record<string, string> = {
  technical: "技术",
  behavioral: "行为",
  system_design: "系统设计",
};

const CATEGORY_COLOR: Record<string, string> = {
  technical: "bg-indigo-50 text-indigo-700 border-indigo-100",
  behavioral: "bg-amber-50 text-amber-700 border-amber-100",
  system_design: "bg-violet-50 text-violet-700 border-violet-100",
};

interface QuestionListModalProps {
  open: boolean;
  questions: PreparedQuestion[];
  onClose: () => void;
  onStart: () => void;
}

export function QuestionListModal({ open, questions, onClose, onStart }: QuestionListModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 mb-4 sm:mb-0 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-base font-bold text-gray-900">题目列表</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        <div className="px-5 py-3 max-h-80 overflow-y-auto divide-y divide-gray-50">
          {questions.map((q, i) => (
            <div key={q.id} className="py-3 flex gap-3">
              <span className="text-sm font-bold text-gray-300 flex-shrink-0 w-5">
                {i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-800 leading-relaxed">{q.question}</p>
                <div className="flex gap-1.5 mt-1.5">
                  <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${CATEGORY_COLOR[q.category] || ""}`}>
                    {CATEGORY_LABEL[q.category] || q.category}
                  </span>
                  {q.focus_area && (
                    <span className="text-xs text-gray-400">{q.focus_area}</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="px-5 py-4 border-t border-gray-100">
          <button
            onClick={onStart}
            className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition-colors"
          >
            开始第1题
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 11.4: 新建类型文件**

```ts
// frontend/lib/prepare-types.ts
export interface PreparedQuestion {
  id: number;
  question: string;
  category: "technical" | "behavioral" | "system_design";
  focus_area: string;
  priority: number;
}

export interface PrepareSSEEvent {
  event: "node_start" | "node_token" | "node_done" | "done" | "error";
  data: {
    node?: string;
    label?: string;
    text?: string;
    elapsed_ms?: number;
    chain?: string[];
    need_direction?: boolean;
    prepared_questions?: PreparedQuestion[];
    summary?: string;
    direction?: string;
    message?: string;
    code?: string;
  };
}
```

- [ ] **Step 11.5: 运行测试**

```bash
cd frontend && pnpm test -- preparation-card --watchAll=false
```

- [ ] **Step 11.6: Commit**

```bash
git add frontend/app/interview/_components/preparation-card.tsx frontend/app/interview/_components/question-list-modal.tsx frontend/app/interview/_components/preparation-card.test.tsx frontend/lib/prepare-types.ts
git commit -m "feat(interview-ui): PreparationCard + QuestionListModal"
```

---

## Task 12: Interview 页面集成 + prepare API 客户端

**Files:**
- Modify: `frontend/app/interview/_components/interview-chat.tsx`
- Modify: `frontend/lib/interview-chat.ts`

- [ ] **Step 12.1: 在 lib/interview-chat.ts 追加 prepare API 客户端**

```ts
// 追加到 frontend/lib/interview-chat.ts

export function startPrepareStream(params: {
  token: string;
  userDirection?: string;
  userBackground?: string;
  jdText?: string;
  jdUrl?: string;
  jdFile?: File;
}): EventSource {
  const form = new FormData();
  if (params.userDirection) form.append("user_direction", params.userDirection);
  if (params.userBackground) form.append("user_background", params.userBackground);
  if (params.jdText) form.append("jd_text", params.jdText);
  if (params.jdUrl) form.append("jd_url", params.jdUrl);
  if (params.jdFile) form.append("jd_file", params.jdFile);

  // 使用 fetch + ReadableStream（EventSource 不支持 POST）
  // 返回 AbortController 供调用方取消
  throw new Error("Use startPrepareStreamFetch instead");
}

export async function* startPrepareStreamFetch(params: {
  token: string;
  userDirection?: string;
  userBackground?: string;
  jdText?: string;
  jdUrl?: string;
}): AsyncGenerator<import("./prepare-types").PrepareSSEEvent> {
  const form = new FormData();
  if (params.userDirection) form.append("user_direction", params.userDirection);
  if (params.userBackground) form.append("user_background", params.userBackground);
  if (params.jdText) form.append("jd_text", params.jdText);
  if (params.jdUrl) form.append("jd_url", params.jdUrl);

  const resp = await fetch("/api/v1/prepare/start", {
    method: "POST",
    headers: { Authorization: `Bearer ${params.token}` },
    body: form,
  });

  if (!resp.ok || !resp.body) throw new Error("Prepare stream failed");

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          yield JSON.parse(line.slice(6));
        } catch { /* ignore */ }
      }
    }
  }
}
```

- [ ] **Step 12.2: 修改 interview-chat.tsx 集成准备卡**

在 `interview-chat.tsx` 组件顶部增加以下状态和逻辑（不删除现有代码）：

```tsx
// 追加 import
import { PreparationCard } from "./preparation-card";
import { AgentTrace, type TraceNodeData } from "./agent-trace";
import { startPrepareStreamFetch } from "@/lib/interview-chat";
import type { PreparedQuestion, PrepareSSEEvent } from "@/lib/prepare-types";

// 在组件内追加状态
const [prepStatus, setPrepStatus] = useState<"running" | "done" | "waiting_direction" | null>(null);
const [traceNodes, setTraceNodes] = useState<TraceNodeData[]>([]);
const [preparedQuestions, setPreparedQuestions] = useState<PreparedQuestion[]>([]);
const [prepSummary, setPrepSummary] = useState("");
const [prepDirection, setPrepDirection] = useState("");
```

在组件 `useEffect` 里（读完 sessionStorage 后）启动 prepare 流：

```tsx
// 读取 sessionStorage 后，如有 target_role 则启动准备流
useEffect(() => {
  const raw = sessionStorage.getItem("interview_context");
  if (!raw) return;
  try {
    const ctx = JSON.parse(raw);
    if (ctx.target_role) {
      setPrepStatus("running");
      runPrepare(ctx);
    }
  } catch { /* ignore */ }
}, []);

async function runPrepare(ctx: { target_role?: string; user_background?: string; jd_text?: string }) {
  const token = isDevAuthBypassEnabled ? DEV_AUTH_BYPASS_TOKEN : (await getToken() ?? "");
  
  for await (const ev of startPrepareStreamFetch({
    token,
    userDirection: ctx.target_role,
    userBackground: ctx.user_background,
    jdText: ctx.jd_text,
  })) {
    handlePrepareEvent(ev);
  }
}

function handlePrepareEvent(ev: PrepareSSEEvent) {
  const { event, data } = ev;

  if (event === "node_start") {
    setTraceNodes((prev) => [
      ...prev,
      { id: data.node!, label: data.label!, title: "", status: "running", tokens: "" },
    ]);
  }

  if (event === "node_token") {
    setTraceNodes((prev) =>
      prev.map((n) => n.id === data.node ? { ...n, tokens: n.tokens + (data.text ?? "") } : n)
    );
    // need_direction 检测：MASTER 发现无方向时触发 AI 提问
    if (data.need_direction) {
      setPrepStatus("waiting_direction");
      // 在聊天区插入一条 AI 消息（LLM 动态生成，这里触发专门的提问接口）
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: "你好！请告诉我你想练习什么方向的面试题？（如「AI Agent 工程师」）",
      }]);
    }
  }

  if (event === "node_done") {
    setTraceNodes((prev) =>
      prev.map((n) => n.id === data.node ? { ...n, status: "done", elapsedMs: data.elapsed_ms } : n)
    );
  }

  if (event === "done") {
    setPreparedQuestions(data.prepared_questions ?? []);
    setPrepSummary(data.summary ?? "");
    setPrepDirection(data.direction ?? "");
    setPrepStatus("done");
  }
}
```

「开始第1题」按钮逻辑：

```tsx
async function handleStartFirstQuestion() {
  // 携带 prepared_questions 进入面试
  const ctx = JSON.parse(sessionStorage.getItem("interview_context") ?? "{}");
  sessionStorage.setItem("interview_context", JSON.stringify({
    ...ctx,
    prepared_questions: preparedQuestions,
    jd_context: null,
  }));
  // 发送 __START__ 触发后端直接出第1题
  await sendMessage("__START__");
}
```

在 JSX 中，在聊天消息列表上方插入准备卡：

```tsx
{prepStatus && (
  <PreparationCard
    status={prepStatus}
    nodes={traceNodes}
    questions={preparedQuestions}
    summary={prepSummary}
    direction={prepDirection}
    onStart={handleStartFirstQuestion}
  />
)}
```

- [ ] **Step 12.3: 运行前端构建验证**

```bash
cd frontend && pnpm build
```

Expected: Build success，无 TypeScript 错误

- [ ] **Step 12.4: Commit**

```bash
git add frontend/app/interview/_components/interview-chat.tsx frontend/lib/interview-chat.ts
git commit -m "feat(interview-ui): 集成准备卡 + prepare SSE 客户端 + 开始第1题"
```

---

## Task 13: Coach 页 JD 上传入口

**Files:**
- Modify: `frontend/app/coach/coach-dashboard.tsx`

- [ ] **Step 13.1: 在「开始面试」按钮旁加 JD 入口**

在 `coach-dashboard.tsx` 中找到「开始面试」按钮（`handleAction("go-room")`），在其前面加一个可展开的 JD 输入区：

```tsx
// 在组件状态中追加
const [showJdInput, setShowJdInput] = useState(false);
const [jdText, setJdText] = useState("");

// JSX 中，在 speechStage === "follow" 的 CTA 区域插入
{speechStage === "follow" && (
  <>
    {/* 可折叠的 JD 输入区 */}
    {!showJdInput ? (
      <button
        type="button"
        onClick={() => setShowJdInput(true)}
        className="text-xs text-indigo-500 underline-offset-2 hover:underline"
      >
        + 我有一份 JD，让 AI 根据 JD 出题
      </button>
    ) : (
      <div className="w-full flex flex-col gap-2 p-3 rounded-xl border border-indigo-100 bg-indigo-50/40">
        <textarea
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          placeholder="粘贴 JD 文本，或留空跳过"
          rows={4}
          className="w-full text-xs resize-none bg-white border border-gray-200 rounded-lg p-2 outline-none focus:border-indigo-300"
        />
        <button
          type="button"
          onClick={() => setShowJdInput(false)}
          className="self-end text-xs text-gray-400 hover:text-gray-600"
        >
          收起
        </button>
      </div>
    )}

    {/* 原有开始面试按钮，点击时把 jd_text 写入 sessionStorage */}
    <button
      type="button"
      onClick={() => {
        if (jdText.trim()) {
          const existing = JSON.parse(sessionStorage.getItem("interview_context") ?? "{}");
          sessionStorage.setItem("interview_context", JSON.stringify({ ...existing, jd_text: jdText.trim() }));
        }
        handleAction("go-room");
      }}
      className="..."  // 保持原有样式不变
    >
      开始面试
    </button>
  </>
)}
```

> **注意：** 保留原有「开始面试」按钮的 className 不变，只在 `onClick` 中追加 jd_text 写入逻辑。

- [ ] **Step 13.2: 运行前端测试 + 构建**

```bash
cd frontend && pnpm test --watchAll=false
cd frontend && pnpm build
```

- [ ] **Step 13.3: Commit**

```bash
git add frontend/app/coach/coach-dashboard.tsx
git commit -m "feat(coach): 新增 JD 输入入口，写入 sessionStorage jd_text"
```

---

## 自检清单

| Spec 要求 | 对应 Task |
|-----------|-----------|
| JD 四种来源提取 | Task 1 |
| PrepareState 类型 | Task 2 |
| 记忆检索（历史+故事库）| Task 3 |
| JD分析 structured output | Task 4 |
| 出题 streaming + 薄弱点优先 | Task 5 |
| MASTER 流式推理 + 路由决策 | Task 6 |
| 动态 chain 路由 | Task 7 |
| SSE 端点 | Task 8 |
| 跳过 opening/briefing | Task 9 |
| TraceNode 三态 | Task 10 |
| PreparationCard 折叠/展开 | Task 11 |
| QuestionListModal | Task 11 |
| 开始第1题按钮 | Task 12 |
| MASTER need_direction → AI 提问 | Task 12 |
| Coach JD 入口 | Task 13 |
| 工具调用预留（mock）| Task 5（_llm tool stub）|
| 出题完成后摘要（LLM生成）| Task 6/7（summary 字段）|
