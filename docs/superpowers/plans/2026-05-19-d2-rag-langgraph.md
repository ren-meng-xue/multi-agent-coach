# D2 - RAG 题库 + LangGraph 骨架（8h）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 RAG 题库摄入流水线（Firecrawl 抓 5 个文档源 → chunk → embedding → 入 `rag_chunks`），实现 `search_rag` 向量检索 helper；建立 LangGraph `StateGraph` 空骨架（5 节点占位，能 START → END 跑通）。

**Architecture:** `scripts/seed_rag.py` 调用 `app.services.rag.ingest` 流水线：fetch（Firecrawl）→ chunk（递归按字符切，500-800 token，overlap 100）→ embed（OpenAI text-embedding-3-small）→ upsert（SQLAlchemy）。`app.services.rag.retrieve.search_rag(query, top_k=5)` 用 pgvector L2 距离检索。LangGraph 用 `langgraph.graph.StateGraph(InterviewState)` 注册 5 个空节点 + 顺序边，编译后能跑通空 invoke。

**Tech Stack:** Firecrawl Python SDK / OpenAI Embedding / SQLAlchemy 2 async / pgvector / LangGraph 0.2+ / TypedDict。

**输入：** D1 EOD commit。`./dev.sh` 起服务正常，`alembic current` 显示 head，`/health` 返回 ok。

**输出：** D2 EOD commit `feat: RAG 摄入 + LangGraph 骨架`。`rag_chunks` 表 ≥ 100 行；`pytest tests/test_rag.py` 全绿；空图能跑通 invoke。

---

## Task 1: OpenAI Embedding 客户端封装

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/rag/__init__.py`
- Create: `backend/app/services/llm/__init__.py`
- Create: `backend/app/services/llm/openai_client.py`
- Test: `backend/tests/unit/test_openai_client.py`

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm.openai_client import embed_texts


@pytest.mark.asyncio
async def test_embed_texts_returns_vectors():
    fake_response = type(
        "R",
        (),
        {
            "data": [
                type("E", (), {"embedding": [0.1] * 1536})(),
                type("E", (), {"embedding": [0.2] * 1536})(),
            ]
        },
    )()
    with patch(
        "app.services.llm.openai_client._client.embeddings.create",
        new=AsyncMock(return_value=fake_response),
    ):
        out = await embed_texts(["hello", "world"])
    assert len(out) == 2
    assert len(out[0]) == 1536


@pytest.mark.asyncio
async def test_embed_texts_empty_input_returns_empty():
    out = await embed_texts([])
    assert out == []
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_openai_client.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `app/services/llm/openai_client.py`**

```python
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.services.llm")

_settings = get_settings()
_client = AsyncOpenAI(api_key=_settings.openai_api_key.get_secret_value())


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    resp = await _client.embeddings.create(
        model=_settings.openai_model_embedding,
        input=texts,
    )
    return [item.embedding for item in resp.data]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def chat_complete(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    response_format: dict | None = None,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
) -> dict:
    kwargs = {
        "model": model or _settings.openai_model_chat,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    resp = await _client.chat.completions.create(**kwargs)
    return resp.model_dump()


async def chat_stream(messages: list[dict], model: str | None = None, temperature: float = 0.7):
    """Async generator yielding token deltas."""
    stream = await _client.chat.completions.create(
        model=model or _settings.openai_model_chat,
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
```

- [ ] **Step 4: 加 `__init__.py`**

```bash
touch backend/app/services/__init__.py backend/app/services/rag/__init__.py backend/app/services/llm/__init__.py
```

- [ ] **Step 5: 跑测试通过**

```bash
cd backend && uv run pytest tests/unit/test_openai_client.py -v
```
Expected: 2 passed。

- [ ] **Step 6: commit**

```bash
git add backend/app/services/__init__.py backend/app/services/rag/__init__.py backend/app/services/llm/__init__.py backend/app/services/llm/openai_client.py backend/tests/unit/test_openai_client.py
git commit -m "feat(llm): add openai client with retry, embed/chat/stream"
```

---

## Task 2: chunk 切分逻辑

**Files:**
- Create: `backend/app/services/rag/chunker.py`
- Test: `backend/tests/unit/test_chunker.py`

- [ ] **Step 1: 写失败测试**

```python
from app.services.rag.chunker import chunk_text


def test_chunk_text_under_size_returns_single_chunk():
    text = "hello world"
    chunks = chunk_text(text, target_tokens=500, overlap_tokens=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_long_input_produces_overlapping_chunks():
    paragraph = "Lorem ipsum dolor sit amet, " * 200  # 5600 字符约 ~1500 token
    chunks = chunk_text(paragraph, target_tokens=500, overlap_tokens=100)
    assert len(chunks) >= 2
    # 重叠检查：后一个 chunk 的开头应包含前一个 chunk 的尾部
    tail = chunks[0][-300:]
    head = chunks[1][:600]
    assert any(word in head for word in tail.split() if len(word) > 4)


def test_chunk_text_respects_paragraph_boundary_when_possible():
    text = "Para 1 line 1.\nPara 1 line 2.\n\nPara 2 line 1.\n\nPara 3 line 1."
    chunks = chunk_text(text, target_tokens=20, overlap_tokens=5)
    # 至少不会把单个句子切两半（rough check）
    for c in chunks:
        assert len(c) > 0
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_chunker.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `app/services/rag/chunker.py`**

```python
from __future__ import annotations

CHAR_PER_TOKEN = 4  # 粗略估算：英文 ~4 字符/token，中文混合略低，足够 D2 demo


def chunk_text(
    text: str,
    target_tokens: int = 600,
    overlap_tokens: int = 100,
) -> list[str]:
    if not text:
        return []
    target_chars = target_tokens * CHAR_PER_TOKEN
    overlap_chars = overlap_tokens * CHAR_PER_TOKEN

    if len(text) <= target_chars:
        return [text.strip()] if text.strip() else []

    chunks: list[str] = []
    cursor = 0
    n = len(text)
    while cursor < n:
        end = min(cursor + target_chars, n)
        if end < n:
            # 倾向在段落 / 句子边界切断
            window = text[cursor:end]
            for sep in ["\n\n", "\n", "。", ".", "!", "?", "？", "！"]:
                idx = window.rfind(sep)
                if idx > target_chars * 0.5:  # 不要切得太前
                    end = cursor + idx + len(sep)
                    break
        chunk = text[cursor:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        cursor = max(end - overlap_chars, cursor + 1)
    return chunks
```

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/unit/test_chunker.py -v
```
Expected: 3 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/rag/chunker.py backend/tests/unit/test_chunker.py
git commit -m "feat(rag): add chunk_text with token-budget overlap"
```

---

## Task 3: pgvector 检索 helper

**Files:**
- Create: `backend/app/services/rag/retrieve.py`
- Test: `backend/tests/integration/test_rag_retrieve.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from sqlalchemy import delete

from app.models.core import RagChunk
from app.services.rag.retrieve import search_rag


@pytest.mark.asyncio
async def test_search_rag_returns_top_k(db):
    await db.execute(delete(RagChunk).where(RagChunk.source == "test"))
    await db.flush()
    # 插入 3 个测试 chunk，embedding 用确定向量
    embs = [
        [1.0] + [0.0] * 1535,  # 与 query 接近
        [0.0, 1.0] + [0.0] * 1534,
        [0.0, 0.0, 1.0] + [0.0] * 1533,
    ]
    for i, e in enumerate(embs):
        db.add(
            RagChunk(
                source="test",
                title=f"t{i}",
                content=f"content {i}",
                embedding=e,
                metadata_json={"idx": i},
            )
        )
    await db.flush()

    query_emb = [1.0] + [0.0] * 1535
    results = await search_rag(db, query_emb, top_k=2, sources=["test"])
    assert len(results) == 2
    assert results[0].title == "t0"  # 最相似的应该排第一


@pytest.mark.asyncio
async def test_search_rag_empty_db_returns_empty(db):
    await db.execute(delete(RagChunk).where(RagChunk.source == "test"))
    await db.flush()
    out = await search_rag(db, [0.5] * 1536, top_k=5, sources=["test"])
    assert out == []
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/integration/test_rag_retrieve.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `app/services/rag/retrieve.py`**

```python
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import RagChunk


async def search_rag(
    db: AsyncSession,
    query_embedding: Sequence[float],
    top_k: int = 5,
    sources: list[str] | None = None,
) -> list[RagChunk]:
    stmt = select(RagChunk)
    if sources:
        stmt = stmt.where(RagChunk.source.in_(sources))
    # pgvector cosine distance (<=>) lower = more similar
    stmt = stmt.order_by(RagChunk.embedding.cosine_distance(list(query_embedding))).limit(top_k)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def search_rag_by_text(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    sources: list[str] | None = None,
) -> list[RagChunk]:
    from app.services.llm.openai_client import embed_texts

    embs = await embed_texts([query])
    if not embs:
        return []
    return await search_rag(db, embs[0], top_k=top_k, sources=sources)
```

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/integration/test_rag_retrieve.py -v
```
Expected: 2 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/rag/retrieve.py backend/tests/integration/test_rag_retrieve.py
git commit -m "feat(rag): add pgvector cosine-distance retrieval helpers"
```

---

## Task 4: Firecrawl 客户端封装

**Files:**
- Create: `backend/app/services/rag/firecrawl_client.py`
- Test: `backend/tests/unit/test_firecrawl_client.py`

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import MagicMock, patch

import pytest

from app.services.rag.firecrawl_client import fetch_url_markdown


@pytest.mark.asyncio
async def test_fetch_url_markdown_returns_content():
    fake = MagicMock()
    fake.scrape_url.return_value = MagicMock(
        markdown="# Hello\n\nWorld", metadata={"title": "Hello"}
    )
    with patch("app.services.rag.firecrawl_client._get_app", return_value=fake):
        result = await fetch_url_markdown("https://example.com")
    assert result is not None
    assert result["markdown"].startswith("# Hello")
    assert result["title"] == "Hello"


@pytest.mark.asyncio
async def test_fetch_url_markdown_handles_failure():
    fake = MagicMock()
    fake.scrape_url.side_effect = RuntimeError("upstream")
    with patch("app.services.rag.firecrawl_client._get_app", return_value=fake):
        result = await fetch_url_markdown("https://example.com")
    assert result is None
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_firecrawl_client.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `app/services/rag/firecrawl_client.py`**

```python
import asyncio
from typing import Any

from firecrawl import FirecrawlApp

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.services.rag.firecrawl")

_app: FirecrawlApp | None = None


def _get_app() -> FirecrawlApp:
    global _app
    if _app is None:
        _app = FirecrawlApp(api_key=get_settings().firecrawl_api_key.get_secret_value())
    return _app


async def fetch_url_markdown(url: str) -> dict[str, Any] | None:
    loop = asyncio.get_event_loop()
    try:
        app = _get_app()
        resp = await loop.run_in_executor(
            None,
            lambda: app.scrape_url(url, formats=["markdown"]),
        )
        markdown = getattr(resp, "markdown", None) or (resp.get("markdown") if isinstance(resp, dict) else None)
        metadata = getattr(resp, "metadata", None) or (resp.get("metadata", {}) if isinstance(resp, dict) else {})
        if not markdown:
            log.warning("firecrawl_empty_markdown", url=url)
            return None
        return {
            "markdown": markdown,
            "title": metadata.get("title") if isinstance(metadata, dict) else None,
            "metadata": metadata,
        }
    except Exception as exc:
        log.exception("firecrawl_failed", url=url, error=str(exc))
        return None
```

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/unit/test_firecrawl_client.py -v
```
Expected: 2 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/rag/firecrawl_client.py backend/tests/unit/test_firecrawl_client.py
git commit -m "feat(rag): wrap firecrawl scrape into async helper"
```

---

## Task 5: RAG 摄入流水线（ingest）

**Files:**
- Create: `backend/app/services/rag/ingest.py`
- Test: `backend/tests/integration/test_rag_ingest.py`

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select, func

from app.models.core import RagChunk
from app.services.rag.ingest import ingest_url


@pytest.mark.asyncio
async def test_ingest_url_writes_chunks(db):
    await db.execute(delete(RagChunk).where(RagChunk.source == "test_ingest"))
    await db.flush()

    fake_doc = {
        "markdown": "Para 1.\n\n" + ("Lorem ipsum. " * 300),
        "title": "Test",
        "metadata": {"url": "https://example.com/x"},
    }
    fake_embeddings = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536, [0.4] * 1536]

    with patch("app.services.rag.ingest.fetch_url_markdown", new=AsyncMock(return_value=fake_doc)):
        with patch(
            "app.services.rag.ingest.embed_texts",
            new=AsyncMock(return_value=fake_embeddings[:2]),
        ):
            n = await ingest_url(db, "https://example.com/x", source="test_ingest")
    assert n >= 1

    count_q = await db.execute(
        select(func.count()).select_from(RagChunk).where(RagChunk.source == "test_ingest")
    )
    count = count_q.scalar_one()
    assert count == n
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/integration/test_rag_ingest.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `app/services/rag/ingest.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.core import RagChunk
from app.services.llm.openai_client import embed_texts
from app.services.rag.chunker import chunk_text
from app.services.rag.firecrawl_client import fetch_url_markdown

log = get_logger("app.services.rag.ingest")


async def ingest_url(
    db: AsyncSession,
    url: str,
    source: str,
    target_tokens: int = 600,
    overlap_tokens: int = 100,
) -> int:
    doc = await fetch_url_markdown(url)
    if not doc or not doc.get("markdown"):
        log.warning("ingest_skip_empty", url=url, source=source)
        return 0

    chunks = chunk_text(
        doc["markdown"], target_tokens=target_tokens, overlap_tokens=overlap_tokens
    )
    if not chunks:
        return 0

    # 分批 embed，每批 ≤ 64
    embeddings: list[list[float]] = []
    batch_size = 64
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        embs = await embed_texts(batch)
        embeddings.extend(embs)

    title = doc.get("title")
    metadata = doc.get("metadata") or {}
    metadata["source_url"] = url

    for content, emb in zip(chunks, embeddings, strict=False):
        db.add(
            RagChunk(
                source=source,
                title=title,
                content=content,
                embedding=emb,
                metadata_json=metadata,
            )
        )
    await db.flush()
    log.info("ingest_done", url=url, source=source, chunks=len(chunks))
    return len(chunks)
```

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/integration/test_rag_ingest.py -v
```
Expected: 1 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/rag/ingest.py backend/tests/integration/test_rag_ingest.py
git commit -m "feat(rag): add ingest pipeline (fetch->chunk->embed->insert)"
```

---

## Task 6: seed_rag CLI 脚本（5 个文档源）

**Files:**
- Create: `scripts/seed_rag.py`
- Create: `scripts/rag_sources.yaml`

- [ ] **Step 1: 写 `scripts/rag_sources.yaml`**

```yaml
sources:
  - source: langgraph
    urls:
      - https://langchain-ai.github.io/langgraph/concepts/low_level/
      - https://langchain-ai.github.io/langgraph/concepts/memory/
      - https://langchain-ai.github.io/langgraph/concepts/multi_agent/
      - https://langchain-ai.github.io/langgraph/how-tos/streaming/

  - source: mem0
    urls:
      - https://docs.mem0.ai/overview
      - https://docs.mem0.ai/core-concepts/memory-operations

  - source: reflexion
    urls:
      - https://arxiv.org/abs/2303.11366

  - source: memgpt
    urls:
      - https://arxiv.org/abs/2310.08560

  - source: mcp
    urls:
      - https://modelcontextprotocol.io/introduction
      - https://modelcontextprotocol.io/specification/2024-11-05/architecture/
```

- [ ] **Step 2: 写 `scripts/seed_rag.py`**

```python
"""Seed RAG knowledge base from configured sources.

Usage:
    uv run python scripts/seed_rag.py            # 摄入所有 sources
    uv run python scripts/seed_rag.py langgraph  # 仅摄入指定 source
"""

import asyncio
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402
from app.services.rag.ingest import ingest_url  # noqa: E402

configure_logging(level="INFO")
log = get_logger("scripts.seed_rag")

CONFIG_PATH = Path(__file__).resolve().parent / "rag_sources.yaml"


async def main(filter_source: str | None = None):
    with CONFIG_PATH.open() as f:
        config = yaml.safe_load(f)

    total = 0
    for entry in config["sources"]:
        source = entry["source"]
        if filter_source and source != filter_source:
            continue
        for url in entry["urls"]:
            async with async_session_factory() as db:
                try:
                    n = await ingest_url(db, url, source=source)
                    await db.commit()
                    log.info("seed_url_done", source=source, url=url, chunks=n)
                    total += n
                except Exception as exc:
                    await db.rollback()
                    log.exception("seed_url_failed", source=source, url=url, error=str(exc))
            await asyncio.sleep(2)  # 礼貌限速
    log.info("seed_total", chunks=total)


if __name__ == "__main__":
    filter_source = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(filter_source))
```

- [ ] **Step 3: 装 yaml 依赖**

```bash
cd backend && uv add pyyaml
```

- [ ] **Step 4: 执行 seed**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach && uv --directory backend run python scripts/seed_rag.py
```
Expected: 看到 `seed_url_done` 多次，最终 `seed_total chunks=N` 其中 N > 100。

⚠️ 若 arxiv PDF 抓取失败：跳过 PDF，先抓 HTML 摘要页（手工改 `rag_sources.yaml` 把 `arxiv.org/abs/...` 换为同论文的官方 GitHub README 或 paperswithcode 摘要页）。

- [ ] **Step 5: 验证数据**

```bash
docker compose exec postgres psql -U coach -d coach -c "SELECT source, COUNT(*) FROM rag_chunks GROUP BY source;"
```
Expected: 每个 source 行数 > 0，总和 > 100。

- [ ] **Step 6: commit**

```bash
git add scripts/seed_rag.py scripts/rag_sources.yaml backend/pyproject.toml backend/uv.lock
git commit -m "feat(rag): seed 5 knowledge sources (langgraph, mem0, reflexion, memgpt, mcp)"
```

---

## Task 7: LangGraph `InterviewState` + 空图骨架

**Files:**
- Create: `backend/app/services/agents/__init__.py`
- Create: `backend/app/services/agents/state.py`
- Create: `backend/app/services/agents/graph.py`
- Create: `backend/app/services/agents/nodes/__init__.py`
- Create: `backend/app/services/agents/nodes/placeholder.py`
- Test: `backend/tests/unit/test_graph.py`

- [ ] **Step 1: 写失败测试**

```python
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
async def test_graph_compiles_and_runs_empty():
    from app.services.agents.graph import build_graph

    graph = build_graph()
    out = await graph.ainvoke(
        {
            "session_id": "s1",
            "user_id": 1,
            "phase": "hr",
            "current_question": "",
            "user_answer": "",
            "retrieved_memory": {},
            "retrieved_rag": [],
            "reflexion_result": {},
            "messages": [],
        }
    )
    assert out["phase"] == "done"
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_graph.py -v
```
Expected: FAIL `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `app/services/agents/state.py`**

```python
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


class InterviewState(TypedDict, total=False):
    session_id: str
    user_id: int
    phase: Literal["hr", "tech", "reflexion", "memory_writer", "coach", "done"]
    current_question: str
    user_answer: str
    retrieved_memory: dict[str, Any]
    retrieved_rag: list[dict[str, Any]]
    reflexion_result: dict[str, Any]
    messages: Annotated[list, add_messages]
```

- [ ] **Step 4: 实现 `app/services/agents/nodes/placeholder.py`**

```python
"""D2 占位节点：仅推进 phase，不调 LLM。D3 起替换为真实节点。"""

from app.services.agents.state import InterviewState


async def hr_placeholder(state: InterviewState) -> dict:
    return {"phase": "tech"}


async def tech_placeholder(state: InterviewState) -> dict:
    return {"phase": "reflexion"}


async def reflexion_placeholder(state: InterviewState) -> dict:
    return {"phase": "memory_writer", "reflexion_result": {}}


async def memory_writer_placeholder(state: InterviewState) -> dict:
    return {"phase": "coach"}


async def coach_placeholder(state: InterviewState) -> dict:
    return {"phase": "done"}
```

- [ ] **Step 5: 实现 `app/services/agents/graph.py`**

```python
from langgraph.graph import END, START, StateGraph

from app.services.agents.nodes.placeholder import (
    coach_placeholder,
    hr_placeholder,
    memory_writer_placeholder,
    reflexion_placeholder,
    tech_placeholder,
)
from app.services.agents.state import InterviewState

# D3 起这里 import 真实节点
HR_NODE = hr_placeholder
TECH_NODE = tech_placeholder
REFLEXION_NODE = reflexion_placeholder
MEMORY_WRITER_NODE = memory_writer_placeholder
COACH_NODE = coach_placeholder


def build_graph():
    g = StateGraph(InterviewState)
    g.add_node("hr_agent", HR_NODE)
    g.add_node("tech_agent", TECH_NODE)
    g.add_node("reflexion", REFLEXION_NODE)
    g.add_node("memory_writer", MEMORY_WRITER_NODE)
    g.add_node("coach_agent", COACH_NODE)

    g.add_edge(START, "hr_agent")
    g.add_edge("hr_agent", "tech_agent")
    g.add_edge("tech_agent", "reflexion")
    g.add_edge("reflexion", "memory_writer")
    g.add_edge("memory_writer", "coach_agent")
    g.add_edge("coach_agent", END)
    return g.compile()
```

- [ ] **Step 6: 加 `__init__.py`**

```bash
touch backend/app/services/agents/__init__.py backend/app/services/agents/nodes/__init__.py
```

- [ ] **Step 7: 跑测试通过**

```bash
cd backend && uv run pytest tests/unit/test_graph.py -v
```
Expected: 2 passed。

- [ ] **Step 8: commit**

```bash
git add backend/app/services/agents/__init__.py backend/app/services/agents/state.py backend/app/services/agents/graph.py backend/app/services/agents/nodes/__init__.py backend/app/services/agents/nodes/placeholder.py backend/tests/unit/test_graph.py
git commit -m "feat(agents): scaffold LangGraph StateGraph with 5 placeholder nodes"
```

---

## Task 8: 验证 LangGraph + RAG 联通（手动 smoke）

**Files:**
- Test: `backend/tests/integration/test_rag_smoke.py`

- [ ] **Step 1: 写集成 smoke 测试**

```python
import pytest

from app.services.rag.retrieve import search_rag_by_text


@pytest.mark.asyncio
async def test_search_rag_seeded_returns_results(db):
    results = await search_rag_by_text(db, "LangGraph multi agent orchestration", top_k=3)
    # 假设 seed_rag 已跑过
    assert len(results) >= 1
    titles = [r.title for r in results if r.title]
    assert any("langgraph" in (r.source or "").lower() or "agent" in (r.content or "").lower() for r in results)
```

- [ ] **Step 2: 跑测试**

```bash
cd backend && uv run pytest tests/integration/test_rag_smoke.py -v
```
Expected: 1 passed（依赖 Task 6 seed 已跑）。如果 seed 数据未入库会失败 — 先回去补 seed。

- [ ] **Step 3: commit**

```bash
git add backend/tests/integration/test_rag_smoke.py
git commit -m "test(rag): add seeded retrieval smoke test"
```

---

## Task 9: D2 EOD 验收 + commit

- [ ] **Step 1: 跑全部测试**

```bash
cd backend && uv run pytest -v
```
Expected: D1 9 + D2 (openai 2 + chunker 3 + retrieve 2 + firecrawl 2 + ingest 1 + graph 2 + smoke 1 = 13) = 22 个全绿。

- [ ] **Step 2: 验收清单核对**

- [ ] OpenAI 客户端封装可用（embed / chat / stream）
- [ ] chunk_text 切分逻辑正确，含 overlap
- [ ] Firecrawl 抓 5 个 source 成功
- [ ] `rag_chunks` 表 ≥ 100 行（命令行验证）
- [ ] pgvector 检索能按相似度返回 top-k
- [ ] LangGraph 空骨架能 invoke 完成 START → END
- [ ] 22 个 pytest 测试全绿

- [ ] **Step 3: 标记 D2 完成**

```bash
git commit --allow-empty -m "feat: D2 EOD - RAG 摄入 + LangGraph 骨架 ✅"
git push
```

---

## 风险与延期预案（D2 专用）

| 风险 | 预案 |
|---|---|
| Firecrawl 速率超限 / API 失败 | `rag_sources.yaml` 砍到 3 个最稳的 URL（LangGraph 文档），保证 chunk 总数 ≥ 50 |
| arxiv PDF 抓取失败 | 改用 paperswithcode 或论文官网 HTML 摘要页；reflexion 和 memgpt 论文都有 GitHub README 可抓 |
| OpenAI embedding 限流 | 分批 ≤ 64 已实现；429 错误时 tenacity 自动重试；如频繁失败可换 `text-embedding-3-large` 或 batch API |
| LangGraph `add_messages` 导入错误 | 升级到 langgraph ≥ 0.2.50；若仍报错改用 `from langgraph.graph.message import add_messages` 显式路径 |
| chunk overlap 测试 brittle | 测试已用 `any(word in head for word in tail.split())` 放宽断言 |

如果 Task 6 seed 仅完成 < 50 chunks，**仍可进入 D3**，但 D3 技术 Agent 出题质量会下降——在 D3 Task 5 前补够 RAG。
