# D5 - L3 STAR + L4 弱点 + Reflexion（8h）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 D3 占位 `reflexion_node` 和 `memory_writer_node` 替换为真实实现：Reflexion 输出结构化 JSON（评分 + 改进 + 弱点）；memory_writer 把 STAR 抽取写 L3，弱点写 L4，分数 EMA 写 L2，全链路 reflexion_payload 写 interview_message。

**Architecture:** `app.services.reflexion.evaluator.run_reflexion(answer, question)` 用 OpenAI Function Call 输出 Pydantic 校验的 `ReflexionResult`。`app.services.memory.star_extractor.extract_star(answer)` 用 Function Call 输出 STAR 结构 + 去重写入。`app.services.memory.weakness_writer.upsert_weaknesses(user_id, tags)` 处理 occurrence_count 累加。

**Tech Stack:** OpenAI Function Call / Pydantic v2 strict / pgvector cosine_distance 去重 / tenacity 重试。

**输入：** D4 EOD commit。第二次面试 HR Agent 能引用上次内容。

> ⚠️ **D1 起全局变更**：`user_id` 为 `str`（Clerk user_id），所有涉及 `user_id` 的函数签名和测试 fixture 用字符串。API 通过 `Depends(get_current_user_id)` 获取当前用户。集成测试用 `patch_auth()` mock auth。

**输出：** D5 EOD commit `feat: L3 STAR + L4 弱点 + Reflexion 单轮`。一题答完后 L2/L3/L4 全部有数据；reflexion_payload 完整写入 interview_message。

---

## Task 1: ReflexionResult Pydantic Schema

**Files:**
- Create: `backend/app/services/reflexion/__init__.py`
- Create: `backend/app/services/reflexion/schema.py`
- Test: `backend/tests/unit/test_reflexion_schema.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from pydantic import ValidationError

from app.services.reflexion.schema import ReflexionResult, WeaknessTagDelta


def test_reflexion_result_valid():
    r = ReflexionResult(
        scores={"clarity": 7, "depth": 5, "specificity": 6, "STAR_completeness": 4},
        strengths=["逻辑清晰"],
        gaps=["缺量化"],
        improvement_suggestion="补充量化结果",
        follow_up_question="再讲讲 trade-off",
        weakness_tags_to_add=[
            WeaknessTagDelta(tag="star-缺量化", category="star", severity=0.6)
        ],
    )
    assert r.scores["clarity"] == 7
    assert r.weakness_tags_to_add[0].tag == "star-缺量化"


def test_reflexion_result_score_range():
    with pytest.raises(ValidationError):
        ReflexionResult(
            scores={"clarity": 15, "depth": 5, "specificity": 6, "STAR_completeness": 4},
            strengths=[], gaps=[], improvement_suggestion="x", follow_up_question="y",
        )


def test_reflexion_result_required_score_keys():
    with pytest.raises(ValidationError):
        ReflexionResult(
            scores={"clarity": 7},  # 缺其他维度
            strengths=[], gaps=[], improvement_suggestion="x", follow_up_question="y",
        )


def test_function_schema_export():
    from app.services.reflexion.schema import REFLEXION_TOOL_SCHEMA
    assert REFLEXION_TOOL_SCHEMA["type"] == "function"
    assert REFLEXION_TOOL_SCHEMA["function"]["name"] == "reflexion_result"
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_reflexion_schema.py -v
```
Expected: FAIL。

- [ ] **Step 3: 实现 `app/services/reflexion/schema.py`**

```python
from pydantic import BaseModel, Field, model_validator


class WeaknessTagDelta(BaseModel):
    tag: str
    category: str = Field(description="tech / soft / star")
    severity: float = Field(ge=0.0, le=1.0)


class ReflexionResult(BaseModel):
    scores: dict[str, int] = Field(description="4 个固定维度 clarity/depth/specificity/STAR_completeness，每个 1-10")
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    improvement_suggestion: str
    follow_up_question: str
    weakness_tags_to_add: list[WeaknessTagDelta] = Field(default_factory=list)
    star_extracted: dict | None = Field(default=None, description="如果回答含项目经历，抽出 STAR 结构")

    REQUIRED_DIMS = {"clarity", "depth", "specificity", "STAR_completeness"}

    @model_validator(mode="after")
    def check_scores(self):
        missing = self.REQUIRED_DIMS - set(self.scores.keys())
        if missing:
            raise ValueError(f"missing score dimensions: {missing}")
        for k, v in self.scores.items():
            if not (1 <= v <= 10):
                raise ValueError(f"score {k}={v} out of range 1-10")
        return self


REFLEXION_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "reflexion_result",
        "description": "提交对候选人回答的评分、反思与改进建议。",
        "parameters": {
            "type": "object",
            "properties": {
                "scores": {
                    "type": "object",
                    "description": "4 个固定维度评分",
                    "properties": {
                        "clarity": {"type": "integer", "minimum": 1, "maximum": 10},
                        "depth": {"type": "integer", "minimum": 1, "maximum": 10},
                        "specificity": {"type": "integer", "minimum": 1, "maximum": 10},
                        "STAR_completeness": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["clarity", "depth", "specificity", "STAR_completeness"],
                },
                "strengths": {"type": "array", "items": {"type": "string"}},
                "gaps": {"type": "array", "items": {"type": "string"}},
                "improvement_suggestion": {"type": "string"},
                "follow_up_question": {"type": "string"},
                "weakness_tags_to_add": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tag": {"type": "string"},
                            "category": {"type": "string"},
                            "severity": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["tag", "category", "severity"],
                    },
                },
                "star_extracted": {
                    "type": ["object", "null"],
                    "properties": {
                        "project_name": {"type": "string"},
                        "situation": {"type": "string"},
                        "task": {"type": "string"},
                        "action": {"type": "string"},
                        "result": {"type": "string"},
                        "quantified_results": {"type": "string"},
                        "tech_stack": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "required": [
                "scores", "strengths", "gaps",
                "improvement_suggestion", "follow_up_question", "weakness_tags_to_add",
            ],
        },
    },
}
```

- [ ] **Step 4: 加 `__init__.py`**

```bash
touch backend/app/services/reflexion/__init__.py
```

- [ ] **Step 5: 跑测试通过**

```bash
cd backend && uv run pytest tests/unit/test_reflexion_schema.py -v
```
Expected: 4 passed。

- [ ] **Step 6: commit**

```bash
git add backend/app/services/reflexion/__init__.py backend/app/services/reflexion/schema.py backend/tests/unit/test_reflexion_schema.py
git commit -m "feat(reflexion): add ReflexionResult schema + OpenAI function tool definition"
```

---

## Task 2: Reflexion Evaluator（调 LLM 走 function call）

**Files:**
- Create: `backend/app/services/reflexion/evaluator.py`
- Test: `backend/tests/unit/test_reflexion_evaluator.py`

- [ ] **Step 1: 写失败测试**

```python
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.reflexion.evaluator import run_reflexion


@pytest.mark.asyncio
async def test_run_reflexion_parses_tool_call():
    payload = {
        "scores": {"clarity": 7, "depth": 5, "specificity": 6, "STAR_completeness": 4},
        "strengths": ["逻辑清晰"],
        "gaps": ["缺量化"],
        "improvement_suggestion": "补充量化",
        "follow_up_question": "聊聊 trade-off",
        "weakness_tags_to_add": [{"tag": "star-缺量化", "category": "star", "severity": 0.6}],
    }
    fake_resp = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {"id": "x", "function": {"name": "reflexion_result", "arguments": json.dumps(payload)}}
                    ]
                }
            }
        ]
    }
    with patch("app.services.reflexion.evaluator.chat_complete", new=AsyncMock(return_value=fake_resp)):
        result = await run_reflexion(
            question="讲讲你的项目", answer="我做过 LangGraph", topic="LangGraph"
        )
    assert result.scores["clarity"] == 7
    assert result.weakness_tags_to_add[0].tag == "star-缺量化"


@pytest.mark.asyncio
async def test_run_reflexion_retries_on_invalid_output():
    bad = {
        "choices": [{"message": {"tool_calls": [{"id": "x", "function": {"name": "reflexion_result", "arguments": "{}"}}]}}]
    }
    good_payload = {
        "scores": {"clarity": 5, "depth": 5, "specificity": 5, "STAR_completeness": 5},
        "strengths": [], "gaps": [], "improvement_suggestion": "x",
        "follow_up_question": "y", "weakness_tags_to_add": [],
    }
    good = {
        "choices": [{"message": {"tool_calls": [{"id": "x", "function": {"name": "reflexion_result", "arguments": json.dumps(good_payload)}}]}}]
    }
    call_count = {"n": 0}

    async def fake(*a, **kw):
        call_count["n"] += 1
        return bad if call_count["n"] == 1 else good

    with patch("app.services.reflexion.evaluator.chat_complete", new=fake):
        result = await run_reflexion("q", "a", topic=None)
    assert call_count["n"] >= 2
    assert result.scores["clarity"] == 5
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/unit/test_reflexion_evaluator.py -v
```
Expected: FAIL。

- [ ] **Step 3: 实现 `app/services/reflexion/evaluator.py`**

```python
import json

from pydantic import ValidationError

from app.core.logging import get_logger
from app.services.llm.openai_client import chat_complete
from app.services.reflexion.schema import REFLEXION_TOOL_SCHEMA, ReflexionResult

log = get_logger("app.reflexion.evaluator")

SYSTEM = """你是面试 Reflexion 评估器。基于候选人回答，输出严格的结构化评分。
评分基准（1-10）：
- clarity 表达清晰度：是否逻辑通畅、术语准确
- depth 技术深度：是否触及实现/原理/trade-off
- specificity 具体度：是否给出数字、版本、参数等具体细节
- STAR_completeness：S/T/A/R 四要素的完整度（如不涉及项目经历此项给 5）

低分（< 5）维度必须 propose `weakness_tags_to_add`。如果回答含项目经历，必须填 `star_extracted`。"""


async def run_reflexion(
    question: str,
    answer: str,
    topic: str | None = None,
    max_attempts: int = 3,
) -> ReflexionResult:
    user = f"题目：{question}\n\n候选人回答：{answer}\n\n主题：{topic or '通用'}"

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await chat_complete(
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                temperature=0.2,
                tools=[REFLEXION_TOOL_SCHEMA],
                tool_choice={"type": "function", "function": {"name": "reflexion_result"}},
            )
            tool_calls = resp["choices"][0]["message"].get("tool_calls") or []
            if not tool_calls:
                raise ValueError("no tool_calls in response")
            args_raw = tool_calls[0]["function"]["arguments"]
            payload = json.loads(args_raw)
            return ReflexionResult.model_validate(payload)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            log.warning("reflexion_invalid", attempt=attempt, error=str(exc))
            continue
    raise RuntimeError(f"reflexion failed after {max_attempts} attempts: {last_error}")
```

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/unit/test_reflexion_evaluator.py -v
```
Expected: 2 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/reflexion/evaluator.py backend/tests/unit/test_reflexion_evaluator.py
git commit -m "feat(reflexion): add evaluator with function-call + 3x retry"
```

---

## Task 3: STAR 入库（含同项目去重）

**Files:**
- Create: `backend/app/services/memory/star_writer.py`
- Test: `backend/tests/integration/test_star_writer.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from sqlalchemy import delete, select, func
from unittest.mock import AsyncMock, patch

from app.models.core import StarStory, User
from app.services.memory.star_writer import upsert_star_story


@pytest.mark.asyncio
async def test_insert_new_star(db):
    await db.execute(delete(StarStory).where(StarStory.user_id == 1))
    await db.flush()
    if not (await db.get(User, 1)):
        db.add(User(id=1, email="u1@example.com"))
        await db.flush()

    fake_emb = AsyncMock(return_value=[[0.1] * 1536])
    with patch("app.services.memory.star_writer.embed_texts", new=fake_emb):
        await upsert_star_story(
            db, user_id=1,
            star={
                "project_name": "LangGraph 多步调研",
                "situation": "团队要做内部知识助手",
                "task": "实现多步检索",
                "action": "用 StateGraph",
                "result": "上线服务 5 个团队",
                "quantified_results": "QPS 30+",
                "tech_stack": ["LangGraph", "FastAPI"],
            },
            quality_score=0.7,
        )
    await db.flush()
    c = await db.execute(select(func.count()).select_from(StarStory).where(StarStory.user_id == 1))
    assert c.scalar_one() == 1


@pytest.mark.asyncio
async def test_dedupe_same_project_by_embedding_similarity(db):
    await db.execute(delete(StarStory).where(StarStory.user_id == 1))
    await db.flush()
    if not (await db.get(User, 1)):
        db.add(User(id=1, email="u1@example.com"))
        await db.flush()

    fake_emb = AsyncMock(return_value=[[0.5] * 1536])  # 两次都返回相同 embedding
    with patch("app.services.memory.star_writer.embed_texts", new=fake_emb):
        await upsert_star_story(
            db, user_id=1,
            star={"project_name": "X", "situation": "s1", "task": "t", "action": "a", "result": "r"},
            quality_score=0.5,
        )
        await db.flush()
        await upsert_star_story(
            db, user_id=1,
            star={"project_name": "X", "situation": "s2-updated", "task": "t", "action": "a", "result": "r"},
            quality_score=0.8,
        )
    await db.flush()
    c = await db.execute(select(func.count()).select_from(StarStory).where(StarStory.user_id == 1))
    assert c.scalar_one() == 1  # 应保留 1 条
    s = (await db.execute(select(StarStory).where(StarStory.user_id == 1))).scalar_one()
    assert s.quality_score == 0.8  # 高质量版本胜出
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/integration/test_star_writer.py -v
```
Expected: FAIL。

- [ ] **Step 3: 实现 `app/services/memory/star_writer.py`**

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.core import StarStory
from app.services.llm.openai_client import embed_texts

log = get_logger("app.memory.star_writer")

DEDUPE_THRESHOLD = 0.15  # cosine_distance < 0.15 视为同一项目（约 cos_sim > 0.85）


def _star_signature(star: dict) -> str:
    parts = [
        star.get("project_name") or "",
        star.get("situation") or "",
        star.get("action") or "",
        " ".join(star.get("tech_stack") or []),
    ]
    return "\n".join(p for p in parts if p)


async def upsert_star_story(
    db: AsyncSession,
    user_id: int,
    star: dict,
    quality_score: float = 0.5,
    source_message_id: uuid.UUID | None = None,
) -> StarStory:
    sig = _star_signature(star)
    embs = await embed_texts([sig])
    emb = embs[0] if embs else None

    if emb is not None:
        candidate_q = (
            select(StarStory)
            .where(StarStory.user_id == user_id)
            .order_by(StarStory.embedding.cosine_distance(emb))
            .limit(1)
        )
        candidate = (await db.execute(candidate_q)).scalar_one_or_none()
        if candidate is not None and candidate.project_name == star.get("project_name"):
            # 同项目去重：更新已有
            if quality_score >= (candidate.quality_score or 0):
                for k in ("situation", "task", "action", "result", "quantified_results", "tech_stack"):
                    if star.get(k):
                        setattr(candidate, k, star[k])
                candidate.quality_score = quality_score
                candidate.embedding = emb
                if source_message_id:
                    candidate.source_message_id = source_message_id
                await db.flush()
                log.info("star_updated_dedupe", user_id=user_id, project=star.get("project_name"))
                return candidate
            else:
                log.info("star_skipped_lower_quality", user_id=user_id, project=star.get("project_name"))
                return candidate

    new = StarStory(
        user_id=user_id,
        project_name=star.get("project_name"),
        situation=star.get("situation"),
        task=star.get("task"),
        action=star.get("action"),
        result=star.get("result"),
        quantified_results=star.get("quantified_results"),
        tech_stack=star.get("tech_stack"),
        quality_score=quality_score,
        source_message_id=source_message_id,
        embedding=emb,
    )
    db.add(new)
    await db.flush()
    log.info("star_inserted", user_id=user_id, project=star.get("project_name"))
    return new
```

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/integration/test_star_writer.py -v
```
Expected: 2 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/memory/star_writer.py backend/tests/integration/test_star_writer.py
git commit -m "feat(memory): add STAR upsert with embedding-based dedupe"
```

---

## Task 4: 弱点标签写入

**Files:**
- Create: `backend/app/services/memory/weakness_writer.py`
- Test: `backend/tests/integration/test_weakness_writer.py`

- [ ] **Step 1: 写失败测试**

```python
import uuid

import pytest
from sqlalchemy import delete, select, func

from app.models.core import User, WeaknessTag
from app.services.memory.weakness_writer import upsert_weaknesses


@pytest.mark.asyncio
async def test_insert_new_weakness(db):
    await db.execute(delete(WeaknessTag).where(WeaknessTag.user_id == 1))
    await db.flush()
    if not (await db.get(User, 1)):
        db.add(User(id=1, email="u1@example.com"))
        await db.flush()
    sid = uuid.uuid4()
    await upsert_weaknesses(
        db, user_id=1,
        tags=[{"tag": "star-缺量化", "category": "star", "severity": 0.6}],
        session_id=sid,
        message_id=uuid.uuid4(),
    )
    await db.flush()
    c = await db.execute(select(func.count()).select_from(WeaknessTag).where(WeaknessTag.user_id == 1))
    assert c.scalar_one() == 1


@pytest.mark.asyncio
async def test_existing_weakness_increments_count_and_ema_severity(db):
    await db.execute(delete(WeaknessTag).where(WeaknessTag.user_id == 1))
    await db.flush()
    if not (await db.get(User, 1)):
        db.add(User(id=1, email="u1@example.com"))
        await db.flush()
    sid = uuid.uuid4()
    msg = uuid.uuid4()
    await upsert_weaknesses(
        db, user_id=1,
        tags=[{"tag": "tech-高并发", "category": "tech", "severity": 0.5}],
        session_id=sid, message_id=msg,
    )
    await db.flush()
    await upsert_weaknesses(
        db, user_id=1,
        tags=[{"tag": "tech-高并发", "category": "tech", "severity": 0.8}],
        session_id=sid, message_id=uuid.uuid4(),
    )
    await db.flush()
    w = (await db.execute(select(WeaknessTag).where(WeaknessTag.user_id == 1, WeaknessTag.tag == "tech-高并发"))).scalar_one()
    assert w.occurrence_count == 2
    assert 0.5 < w.severity < 0.8  # EMA 平滑
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/integration/test_weakness_writer.py -v
```
Expected: FAIL。

- [ ] **Step 3: 实现 `app/services/memory/weakness_writer.py`**

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.core import WeaknessTag
from app.services.memory.ema import ema_update_scalar

log = get_logger("app.memory.weakness_writer")


async def upsert_weaknesses(
    db: AsyncSession,
    user_id: int,
    tags: list[dict],
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    alpha: float = 0.3,
) -> int:
    n = 0
    for t in tags:
        tag = t.get("tag")
        category = t.get("category") or "soft"
        severity = float(t.get("severity") or 0.0)
        if not tag:
            continue

        existing = (
            await db.execute(
                select(WeaknessTag).where(
                    WeaknessTag.user_id == user_id, WeaknessTag.tag == tag
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            db.add(
                WeaknessTag(
                    user_id=user_id,
                    tag=tag,
                    category=category,
                    severity=severity,
                    occurrence_count=1,
                    last_occurred_session=session_id,
                    related_message_ids=[str(message_id)],
                    status="active",
                )
            )
        else:
            existing.severity = ema_update_scalar(existing.severity, severity, alpha=alpha)
            existing.occurrence_count = (existing.occurrence_count or 1) + 1
            existing.last_occurred_session = session_id
            existing.related_message_ids = (existing.related_message_ids or []) + [str(message_id)]
            existing.status = "active"
        n += 1
    await db.flush()
    log.info("weaknesses_upserted", user_id=user_id, count=n)
    return n
```

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/integration/test_weakness_writer.py -v
```
Expected: 2 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/services/memory/weakness_writer.py backend/tests/integration/test_weakness_writer.py
git commit -m "feat(memory): add weakness upsert with EMA severity + occurrence counter"
```

---

## Task 5: 真实 reflexion_node + memory_writer_node

**Files:**
- Modify: `backend/app/services/agents/nodes/reflexion.py`
- Modify: `backend/app/services/agents/nodes/memory_writer.py`
- Modify: `backend/app/services/agents/state.py`（加 `last_message_id` 字段）

- [ ] **Step 1: 给 state 加 `last_message_id`（reflexion 写回需要 fk）**

修改 `app/services/agents/state.py`：

```python
class InterviewState(TypedDict, total=False):
    session_id: str
    user_id: int
    phase: Literal["hr", "tech", "reflexion", "memory_writer", "coach", "done"]
    current_question: str
    user_answer: str
    last_message_id: str | None
    retrieved_memory: dict[str, Any]
    retrieved_rag: list[dict[str, Any]]
    reflexion_result: dict[str, Any]
    messages: Annotated[list, add_messages]
```

- [ ] **Step 2: 重写 `app/services/agents/nodes/reflexion.py`**

```python
import uuid

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.services.agents.state import InterviewState
from app.services.interview_repo import append_message
from app.services.reflexion.evaluator import run_reflexion

log = get_logger("app.agents.reflexion")


async def reflexion_node(state: InterviewState) -> dict:
    answer = state.get("user_answer") or ""
    question = state.get("current_question") or ""
    topic_hint = None
    rag = state.get("retrieved_rag") or []
    if rag:
        topic_hint = rag[0].get("source")

    if not answer.strip():
        log.info("reflexion_skip_empty_answer")
        return {"phase": "memory_writer", "reflexion_result": {"items": []}}

    try:
        result = await run_reflexion(question=question, answer=answer, topic=topic_hint)
    except Exception as exc:
        log.exception("reflexion_failed", error=str(exc))
        return {"phase": "memory_writer", "reflexion_result": {"items": []}}

    # 把 reflexion_payload 写入 interview_message
    last_msg_id = state.get("last_message_id")
    if last_msg_id:
        async with async_session_factory() as db:
            from sqlalchemy import update
            from app.models.core import InterviewMessage
            await db.execute(
                update(InterviewMessage)
                .where(InterviewMessage.id == uuid.UUID(last_msg_id))
                .values(reflexion_payload=result.model_dump())
            )
            await db.commit()

    return {"phase": "memory_writer", "reflexion_result": {"items": [result.model_dump()]}}
```

- [ ] **Step 3: 重写 `app/services/agents/nodes/memory_writer.py`**

```python
import uuid

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.services.agents.state import InterviewState
from app.services.memory.profile_repo import apply_ema_update
from app.services.memory.star_writer import upsert_star_story
from app.services.memory.weakness_writer import upsert_weaknesses

log = get_logger("app.agents.memory_writer")


async def memory_writer_node(state: InterviewState) -> dict:
    user_id = state.get("user_id")
    session_id_str = state.get("session_id")
    items = (state.get("reflexion_result") or {}).get("items") or []
    if not items or not user_id or not session_id_str:
        return {"phase": "coach"}

    session_id = uuid.UUID(session_id_str)
    last_msg_id = state.get("last_message_id")
    msg_uuid = uuid.UUID(last_msg_id) if last_msg_id else uuid.uuid4()

    async with async_session_factory() as db:
        for item in items:
            scores = item.get("scores") or {}
            # 1) L2 EMA：tech_strengths 用 specificity+depth 平均，weaknesses 用低分维度
            strengths_delta: dict[str, float] = {}
            weaknesses_delta: dict[str, float] = {}
            if "depth" in scores and "specificity" in scores:
                topic_score = (scores["depth"] + scores["specificity"]) / 20.0
                # 简化：topic 名暂用 "general"，D6 起可结合 retrieved_rag.source
                strengths_delta["general"] = topic_score
            star_score = scores.get("STAR_completeness", 5) / 10.0
            await apply_ema_update(
                db,
                user_id=user_id,
                strengths_delta=strengths_delta or None,
                weaknesses_delta=weaknesses_delta or None,
                star_completeness_delta=star_score,
                alpha=0.3,
            )

            # 2) L4 weakness
            tags = item.get("weakness_tags_to_add") or []
            if tags:
                await upsert_weaknesses(
                    db, user_id=user_id, tags=tags,
                    session_id=session_id, message_id=msg_uuid,
                )

            # 3) L3 STAR
            star = item.get("star_extracted")
            if star and star.get("project_name"):
                await upsert_star_story(
                    db, user_id=user_id, star=star,
                    quality_score=scores.get("STAR_completeness", 5) / 10.0,
                    source_message_id=msg_uuid,
                )
        await db.commit()
        log.info("memory_written", user_id=user_id, items=len(items))

    return {"phase": "coach"}
```

- [ ] **Step 4: 改 interview API（SSE）传 `last_message_id` 到 state**

修改 `app/api/v1/interview.py`，在 SSE event_generator 内：

- `append_message` 用户答案后拿到 `user_msg.id`
- 把它放到 state：

```python
async with async_session_factory() as db:
    s = await get_session(db, session_id)
    if s is None:
        ...
    user_msg = await append_message(db, session_id, role="user", content=body.user_answer)
    await db.commit()
    user_msg_id = str(user_msg.id)
    msgs = await list_messages(db, session_id)

...

state = {
    "session_id": str(session_id),
    "user_id": s.user_id,
    "phase": "hr" if ... else "tech",
    "messages": history,
    "user_answer": body.user_answer,
    "last_message_id": user_msg_id,
    "retrieved_memory": {},
    "retrieved_rag": [],
    "reflexion_result": {},
}
```

- [ ] **Step 5: commit（含 D3 测试可能需要更新）**

```bash
git add backend/app/services/agents/state.py backend/app/services/agents/nodes/reflexion.py backend/app/services/agents/nodes/memory_writer.py backend/app/api/v1/interview.py
git commit -m "feat(agents): real reflexion + memory_writer nodes (L2/L3/L4 writeback)"
```

---

## Task 6: 端到端集成测试（一题答完后 L2/L3/L4 都有数据）

**Files:**
- Test: `backend/tests/integration/test_full_writeback.py`

- [ ] **Step 1: 写集成测试**

```python
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, func, select

from app.models.core import StarStory, User, UserProfile, WeaknessTag
from app.services.agents.graph import build_graph


@pytest.mark.asyncio
async def test_full_writeback_after_one_session(db):
    await db.execute(delete(StarStory).where(StarStory.user_id == 1))
    await db.execute(delete(WeaknessTag).where(WeaknessTag.user_id == 1))
    await db.execute(delete(UserProfile).where(UserProfile.user_id == 1))
    await db.flush()
    if not (await db.get(User, 1)):
        db.add(User(id=1, email="u1@example.com"))
    await db.commit()

    # 准备 1 条 interview_message 作为 last_message_id
    from app.services.interview_repo import create_session, append_message
    sess = await create_session(db, user_id=1)
    await db.flush()
    msg = await append_message(db, sess.id, role="user", content="我做过 LangGraph 多步调研项目，QPS 30+")
    await db.commit()

    reflexion_payload = {
        "scores": {"clarity": 7, "depth": 6, "specificity": 5, "STAR_completeness": 6},
        "strengths": ["逻辑清晰"],
        "gaps": ["缺更多量化"],
        "improvement_suggestion": "再补量化",
        "follow_up_question": "trade-off？",
        "weakness_tags_to_add": [{"tag": "tech-trade-off", "category": "tech", "severity": 0.6}],
        "star_extracted": {
            "project_name": "LangGraph 多步调研",
            "situation": "团队 KM",
            "task": "调研 Agent",
            "action": "StateGraph",
            "result": "上线 5 团队",
            "quantified_results": "QPS 30+",
            "tech_stack": ["LangGraph", "FastAPI"],
        },
    }
    import json as _json

    async def fake_chat(messages, **kw):
        if kw.get("tools"):
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "x",
                                    "function": {"name": "reflexion_result", "arguments": _json.dumps(reflexion_payload)},
                                }
                            ]
                        }
                    }
                ]
            }
        return {"choices": [{"message": {"content": "[HR_DONE] question"}}]}

    fake_emb = AsyncMock(return_value=[[0.7] * 1536])

    with patch("app.services.agents.nodes.hr.chat_complete", new=fake_chat), \
         patch("app.services.agents.nodes.tech.chat_complete", new=fake_chat), \
         patch("app.services.agents.nodes.coach.chat_complete", new=fake_chat), \
         patch("app.services.reflexion.evaluator.chat_complete", new=fake_chat), \
         patch("app.services.agents.nodes.tech.search_rag_by_text", new=AsyncMock(return_value=[])), \
         patch("app.services.memory.star_writer.embed_texts", new=fake_emb):
        graph = build_graph()
        out = await graph.ainvoke(
            {
                "session_id": str(sess.id),
                "user_id": 1,
                "phase": "tech",
                "current_question": "讲讲你的项目",
                "user_answer": "我做过 LangGraph 多步调研项目，QPS 30+",
                "last_message_id": str(msg.id),
                "messages": [{"role": "user", "content": "..."}],
                "retrieved_memory": {},
                "retrieved_rag": [],
                "reflexion_result": {},
            }
        )
    assert out["phase"] == "done"

    # 验证三表都有数据
    p_count = await db.execute(select(func.count()).select_from(UserProfile).where(UserProfile.user_id == 1))
    s_count = await db.execute(select(func.count()).select_from(StarStory).where(StarStory.user_id == 1))
    w_count = await db.execute(select(func.count()).select_from(WeaknessTag).where(WeaknessTag.user_id == 1))
    assert p_count.scalar_one() == 1
    assert s_count.scalar_one() >= 1
    assert w_count.scalar_one() >= 1
```

- [ ] **Step 2: 跑测试**

```bash
cd backend && uv run pytest tests/integration/test_full_writeback.py -v
```
Expected: 1 passed。

- [ ] **Step 3: commit**

```bash
git add backend/tests/integration/test_full_writeback.py
git commit -m "test(integration): full writeback L2/L3/L4 after one session"
```

---

## Task 7: GET /stars/me 和 /weaknesses/me 接口

**Files:**
- Modify: `backend/app/api/v1/profile.py`（加 2 个新路由）
- Test: `backend/tests/integration/test_stars_weaknesses_api.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_get_stars_me_returns_list():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/stars/me", params={"user_id": 1})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_weaknesses_me_returns_list():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/weaknesses/me", params={"user_id": 1})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
```

- [ ] **Step 2: 跑失败测试**

```bash
cd backend && uv run pytest tests/integration/test_stars_weaknesses_api.py -v
```
Expected: FAIL（路由没注册）。

- [ ] **Step 3: 加 2 个 router 到 `app/api/v1/profile.py`**

```python
from sqlalchemy import desc, select

from app.models.core import StarStory, WeaknessTag


@router.get("/stars/me")
async def list_my_stars(user_id: int = 1, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(StarStory).where(StarStory.user_id == user_id).order_by(desc(StarStory.created_at)).limit(50)
    )
    return [
        {
            "id": str(s.id),
            "project_name": s.project_name,
            "situation": s.situation,
            "task": s.task,
            "action": s.action,
            "result": s.result,
            "quantified_results": s.quantified_results,
            "tech_stack": s.tech_stack,
            "quality_score": s.quality_score,
            "created_at": s.created_at,
        }
        for s in r.scalars().all()
    ]


@router.get("/weaknesses/me")
async def list_my_weaknesses(user_id: int = 1, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(WeaknessTag)
        .where(WeaknessTag.user_id == user_id, WeaknessTag.status == "active")
        .order_by(desc(WeaknessTag.severity))
    )
    return [
        {
            "id": str(w.id),
            "tag": w.tag,
            "category": w.category,
            "severity": w.severity,
            "occurrence_count": w.occurrence_count,
            "updated_at": w.updated_at,
        }
        for w in r.scalars().all()
    ]
```

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/integration/test_stars_weaknesses_api.py -v
```
Expected: 2 passed。

- [ ] **Step 5: commit**

```bash
git add backend/app/api/v1/profile.py backend/tests/integration/test_stars_weaknesses_api.py
git commit -m "feat(api): add /stars/me and /weaknesses/me endpoints"
```

---

## Task 8: D5 EOD 验收 + commit

- [ ] **Step 1: 跑全部测试**

```bash
cd backend && uv run pytest -v
```
Expected: D1-D4 ~52 + D5（schema 4 + evaluator 2 + star 2 + weakness 2 + full_writeback 1 + stars/weaknesses api 2 = 13）共 ~65 个全绿。

- [ ] **Step 2: 端到端浏览器验证**

```bash
./dev.sh &
sleep 8
# 1. 浏览器跑完一场完整面试（讲一个项目，引导含项目经历的答案）
# 2. 看 DB：
docker compose exec postgres psql -U coach -d coach -c "SELECT user_id, total_interviews FROM user_profile WHERE user_id=1;"
docker compose exec postgres psql -U coach -d coach -c "SELECT user_id, project_name, quality_score FROM star_stories WHERE user_id=1;"
docker compose exec postgres psql -U coach -d coach -c "SELECT user_id, tag, severity, occurrence_count FROM weakness_tags WHERE user_id=1;"
docker compose exec postgres psql -U coach -d coach -c "SELECT role, reflexion_payload IS NOT NULL FROM interview_message ORDER BY created_at DESC LIMIT 5;"
kill %1
```
Expected: 三表都有数据；至少 1 条 interview_message 的 reflexion_payload 非空。

- [ ] **Step 3: 验收清单核对**

- [ ] Reflexion 输出严格 JSON（含 4 维度分数 + 改进 + 追问 + 弱点）
- [ ] STAR 抽取入 L3，同项目自动去重
- [ ] 低分（< 5）维度自动生成 weakness_tag
- [ ] 弱点连续出现 2 次以上时 `occurrence_count` 累加
- [ ] L2 EMA 更新 strengths/weaknesses 数值
- [ ] interview_message.reflexion_payload 完整写入
- [ ] `/stars/me` 和 `/weaknesses/me` 返回列表
- [ ] D5 里程碑：完整 M2 后端链路打通

- [ ] **Step 4: 标记 D5 完成**

```bash
git commit --allow-empty -m "feat: D5 EOD - L3 STAR + L4 弱点 + Reflexion 单轮 ✅"
git push
```

---

## 风险与延期预案（D5 专用）

| 风险 | 预案 |
|---|---|
| Reflexion JSON 结构不稳定 | 已经用 OpenAI Function Call + Pydantic 校验 + 3 次重试；如果还失败，把 model 换 `gpt-4o`（更稳） |
| STAR 抽取召回率低 | 在 system prompt 里强调"如果回答含项目经历必须填 star_extracted"；评估器测试一次再调 prompt |
| pgvector cosine_distance 比较失败（embedding 为 None） | star_writer 已 guard `if emb is not None`；空 embedding 跳过去重 |
| L2 EMA 触发频繁 → 数值漂移 | 已用 α=0.3 平滑；保留 history JSON 字段；M3 再加 snapshot |
| memory_writer 在 graph 中卡住（async session 嵌套） | 每个写入用独立 `async with async_session_factory() as db` 隔离 |
| Reflexion 给低分但 tags 列表为空 | system prompt 已要求"低分维度必须 propose weakness_tags_to_add"；评估器层加兜底：scores < 5 时若 tags 为空 → 自动补 1 个通用 tag |

如果 Task 6 端到端测试失败，**D6 不能开始**——前端复盘报告页依赖 L3/L4/L2 都有数据。
