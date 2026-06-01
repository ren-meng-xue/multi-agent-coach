# Phase 3+ Inline Trace Multi-Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `interviewer` LangGraph 重构为真·MASTER 动态调度（master + evaluator + followup + ask_question + closing），同时把准备阶段 PreparationCard 与新建的面试期 TurnTraceCard 统一迁移到聊天流 inline 渲染，让用户每轮都看见多 Agent 协作的 trace 面板。

**Architecture:** 沿用 `prepare/master_node` 已经成熟的「Phase 1 流式推理 bullet + Phase 2 结构化 chain」双相调用范式，把面试阶段的调度集中到一个独立的 `master_node` 里；子 agent 池由 evaluator/followup/ask_question/closing 组成，master 用 LLM 输出 chain；后端 SSE 增加 `node_start/node_token/node_done` 三类事件（与 prepare 完全对齐），前端 messages 数组改为 discriminated union 容纳 trace 消息。

**Tech Stack:** Python 3.12, FastAPI, sse_starlette, LangGraph StateGraph, LangChain ChatOpenAI (with `astream_events` v2), pydantic v2 structured output, tenacity retry, structlog, TypeScript, Next.js App Router, shadcn/ui, EventSource via fetch streaming

---

## 文件结构总览

### 新建文件

```
frontend/app/interview/_components/turn-trace-card.tsx
frontend/app/interview/_components/turn-trace-card.test.tsx
backend/tests/unit/test_interviewer_master_node.py
backend/tests/unit/test_interviewer_evaluator_node.py
backend/tests/unit/test_interviewer_chain_routing.py
backend/tests/unit/test_interviewer_report_aggregate.py
```

### 修改文件

```
backend/app/agents/interviewer/state.py          # 字段瘦身 + turn_evaluations + chain
backend/app/agents/interviewer/prompts.py        # 删除 5 个旧 prompt，新增 5 个
backend/app/agents/interviewer/nodes.py          # 全面重构：删 3 节点函数，新增 2 节点，改造 followup/report
backend/app/agents/interviewer/graph.py          # 全面重构：新 chain 路由
backend/app/services/interview_turn.py           # SSE 事件透传 + state 字段映射调整
backend/app/api/v1/interview.py                  # SSE 透传所有新事件
backend/tests/unit/test_interviewer_graph.py     # 删除 opening/briefing/decide_next 旧测试
backend/tests/integration/test_interview_turn_service.py  # 接入新流程
backend/tests/integration/test_prepare_interview_integration.py  # 端到端流程更新

frontend/lib/prepare-types.ts                    # 抽 TraceNodeStatus / TraceNodeData 等共享类型
frontend/lib/interview-chat.ts                   # onTraceNode 回调 + SSE 事件路由
frontend/app/interview/_components/agent-trace.tsx        # 复用共享类型
frontend/app/interview/_components/trace-node.tsx         # 复用共享类型
frontend/app/interview/_components/preparation-card.tsx   # 调整为可插入到 messages 流的渲染
frontend/app/interview/_components/interview-chat.tsx     # discriminated union + 每轮 inline trace
frontend/app/interview/_components/interview-chat.test.tsx  # 测试更新
frontend/app/interview/_components/preparation-card.test.tsx  # 测试更新
```

### 完全删除（旧 prompt + 旧节点函数 + 旧测试用例）

```
prompts: OPENING_SYSTEM_PROMPT, OPENING_INFO_SYSTEM_PROMPT, BRIEFING_SYSTEM_PROMPT,
         BRIEFING_INTENT_SYSTEM_PROMPT, NOT_READY_SYSTEM_PROMPT, DECIDE_SYSTEM_PROMPT

nodes:   opening_node, briefing_node, decide_next_node,
         generate_opening_reply, generate_briefing_reply, generate_not_ready_reply,
         extract_opening_info, detect_briefing_intent, decide_next_action,
         OpeningInfoOutput, BriefingIntentOutput, DecideNextOutput

state fields: opening_complete, briefing_intent, decision_action, decision_reason, followup_question

graph: opening / briefing / decide_next 节点 + route_after_briefing / route_after_decide
```

---

# Batch A · 后端清理（移除冗余节点）

## Task 1: 移除 InterviewState 中的冗余字段

**Files:**
- Modify: `backend/app/agents/interviewer/state.py`

- [ ] **Step 1: 打开 state.py 并删除 opening/briefing/decide_next 相关字段**

替换 `InterviewState` 类内容为：

```python
"""LangGraph state for the multi-agent interviewer graph."""
from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

InterviewStage = Literal["opening", "interview", "closing"]


class TurnEvaluation(TypedDict, total=False):
    """单轮答题的评估结果，由 evaluator_node 写入。"""

    question_index: int
    followup_index: int
    bullets: list[str]
    technical_depth: float
    quantified_results: float
    failure_tradeoffs: float
    structure: float
    summary_score: float


class InterviewState(TypedDict, total=False):
    """Graph state shared-1 by interviewer nodes."""

    # 基础
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

    # 准备阶段产出（沿用 Phase 3）
    jd_context: dict[str, Any] | None
    prepared_questions: list[dict[str, Any]]
    current_question_index: int

    # MASTER 动态调度
    chain: list[str]                  # 本轮 chain，由 master_node 输出
    master_reason: str                # log 用，不展示
    turn_evaluations: list[TurnEvaluation]  # 累积所有轮次评估，report_node 聚合

    # 报告
    report: dict[str, Any]
```

注意：完全删除了 `opening_complete / briefing_intent / decision_action / decision_reason / followup_question` 五个字段。`InterviewStage` 的 `"briefing"` 也被移除（保留 `"opening" | "interview" | "closing"`，opening 仅作为 DB 兼容值，新逻辑不写入）。

- [ ] **Step 2: 跑现有测试预期它们失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_graph.py -v
```

Expected: 多个 FAIL，因为引用了被删除的字段。后续 task 会清理这些测试。

- [ ] **Step 3: 跑 typecheck 预期它们失败**

```bash
cd backend && .venv/bin/python -m mypy app/agents-1/interviewer
```

Expected: 多处错误指向被删字段。Task 3 / Task 4 会修复。

- [ ] **Step 4: 暂不 commit**

state 改动会让 nodes/graph 报错，等 Task 3、Task 4 一起完成后再统一 commit。

---

## Task 2: 清理 prompts.py 中的冗余 prompt

**Files:**
- Modify: `backend/app/agents/interviewer/prompts.py`

- [ ] **Step 1: 完全重写 prompts.py 为保留 + 新增的精简版**

替换文件内容为：

```python
"""Prompts for the multi-agent interviewer graph."""

# ─────────────────────────────────────────────
# 保留：原有出题/收尾/报告 prompts
# ─────────────────────────────────────────────

QUESTION_SYSTEM_PROMPT = (
    "你是一位资深、冷静且极其专业的技术面试官。你追求的是技术深度和候选人的真实实践。\n"
    "【核心准则】：\n"
    "1. **拒绝廉价赞美**：严禁对候选人的简略回答（如只列举工具名、简单描述概念）进行"
    "\"详细\"、\"清晰\"、\"深刻\"等虚假夸奖。如果候选人回答太浅，请直接指出并要求其深入细节"
    "（例如：\"这个描述比较笼统，请结合具体代码实现谈谈...\"）。\n"
    "2. **客观反馈**：在提出下一题前，可以简要总结对方的观点，但必须保持客观、中立。"
    "只有当对方确实展现出非共识的洞察力或复杂的架构设计时，才给予适度认可。\n"
    "3. **技术上下文对齐**：必须记住并引用候选人提到的具体技术栈（如 pgvector, Cohere, "
    "LangGraph）。追问应直击该技术的痛点或选型权衡，拒绝万金油式的提问。\n"
    "4. **转场自然**：使用专业、简洁的口语化转场。一次只问一个问题。"
)

CLOSING_SYSTEM_PROMPT = (
    "你是一位资深技术面试官。面试已正式结束。\n"
    "【核心任务】：\n"
    "1. **最终点评**：在告知结束前，请对候选人在本次面试中的整体表现做一个简短、专业且中肯的总结。\n"
    "2. **正式告知结束**：明确告知候选人模拟面试已圆满结束。\n"
    "3. **后续指引**：说明详细的结构化评估报告已经生成。\n"
    "【禁令】：严禁再提出任何新问题。\n"
    "语气要专业、真诚、有温度，像一个资深前辈在给后辈建议。"
)

REPORT_FALLBACK_SYSTEM_PROMPT = (
    "你是面试评估专家。请根据完整的面试对话对候选人进行结构化评分。"
    "评分维度各 0-5 分：technical_depth、quantified_results、failure_tradeoffs、structure。"
    "overall_score = 各维度均值 × 2，保留一位小数。"
    "1. highlights：2-3 条具体亮点。\n"
    "2. improvements：2-3 条具体改进建议。\n"
    "3. key_concepts：2-3 个核心技术概念。\n"
    "4. common_mistakes：2 个常见陷阱。\n"
    "所有文字字段必须用中文。"
)

# ─────────────────────────────────────────────
# 新增：MASTER 调度
# ─────────────────────────────────────────────

MASTER_REASONING_PROMPT = (
    "你是 AI 面试委员会的 MASTER 调度器。请仔细看候选人最新的一轮回答，"
    "用 1-2 句中文说出你的判断和决定。\n"
    "【输出要求】：\n"
    "- 必须是连贯的自然中文，不能输出 JSON、不能用 Markdown 标记。\n"
    "- 说清楚两件事：①这轮回答好不好（要不要评估）②下一步该追问、出新题还是收尾。\n"
    "- 例：\"回答覆盖了 CAP 但没量化指标，先评估再追问 QPS 数据。\"\n"
    "- 例：\"候选人跑题了，跳过评估直接拉回主线。\"\n"
    "- 例：\"已经做完 5 道题，该收尾了。\"\n"
    "【上下文】：\n{context}"
)

MASTER_DECISION_PROMPT = (
    "你是 AI 面试委员会的 MASTER 调度器。基于刚才的推理，输出本轮要调度的子 agent chain。\n"
    "【可选 agent】：\n"
    "- evaluator：对本轮回答做 4 维度评分 + 简短点评\n"
    "- followup：在当前题目内追问\n"
    "- ask_question：进入下一道题\n"
    "- closing：结束整场面试\n"
    "【约束】：\n"
    "- chain 不能为空\n"
    "- chain 末尾必须是 followup / ask_question / closing 之一\n"
    "- chain 含 closing 时，closing 必须是最后一个\n"
    "- 一般情况下，followup 或 ask_question 之前都应该跑 evaluator；"
    "  但用户跑题/敷衍时可以跳过 evaluator 直接追问\n"
    "【上下文】：\n{context}"
)

# ─────────────────────────────────────────────
# 新增：evaluator
# ─────────────────────────────────────────────

EVALUATOR_REASONING_PROMPT = (
    "你是 AI 面试委员会的评估官。请用 2-3 条要点简短点评候选人本轮回答。\n"
    "【输出要求】：\n"
    "- 每条要点一行，开头用 \"·\"，每行不超过 30 字。\n"
    "- 不能输出 JSON 或 Markdown 标记。\n"
    "- 直击事实，例如：\"·覆盖了 CAP 但未给量化指标\"。\n"
    "【上下文】：\n{context}"
)

EVALUATOR_SCORING_PROMPT = (
    "你是 AI 面试委员会的评估官。请对候选人本轮回答打 4 维度分（各 0-10 分）。\n"
    "【维度】：\n"
    "- technical_depth：技术深度\n"
    "- quantified_results：是否给出量化指标\n"
    "- failure_tradeoffs：失败/降级/权衡的考虑\n"
    "- structure：表达结构完整性\n"
    "summary_score = 4 维度均值，保留一位小数。\n"
    "bullets 字段填入刚才输出的 2-3 条要点（去掉行首 · 符号）。\n"
    "【上下文】：\n{context}"
)

# ─────────────────────────────────────────────
# 新增：followup（替代旧 followup_question）
# ─────────────────────────────────────────────

FOLLOWUP_SYSTEM_PROMPT = (
    "你是一位资深技术面试官。基于候选人最近一轮回答，提出一个深挖追问。\n"
    "【准则】：\n"
    "1. 一次只问一个问题。\n"
    "2. 追问必须基于回答中的具体内容，不能是万金油问题。\n"
    "3. 优先追问回答中缺失的关键点（量化数据、失败处理、技术选型理由）。\n"
    "4. 语气专业、克制，不要赞美也不要批评。"
)

# ─────────────────────────────────────────────
# 新增：report 聚合
# ─────────────────────────────────────────────

REPORT_AGGREGATE_SYSTEM_PROMPT = (
    "你是面试评估总结专家。根据每轮已经打好的分数 + 整场对话内容，生成结构化总报告。"
    "【输入】：每轮的评估摘要已附在上下文。\n"
    "【你的任务】：\n"
    "1. highlights：从所有 bullets 中提炼 2-3 条最突出的亮点。\n"
    "2. improvements：提炼 2-3 条最关键的改进建议。\n"
    "3. key_concepts：提取 2-3 个核心技术概念。\n"
    "4. common_mistakes：总结 2 个本场暴露的典型误区。\n"
    "5. 4 维度分数 + overall_score 由系统按平均值计算并已附在上下文，请直接复用，不要重新评分。\n"
    "所有文字字段必须用中文。"
)
```

- [ ] **Step 2: 跑 import 检查**

```bash
cd backend && .venv/bin/python -c "from app.agents.interviewer import prompts; print(dir(prompts))"
```

Expected: 输出包含 `QUESTION_SYSTEM_PROMPT, CLOSING_SYSTEM_PROMPT, REPORT_FALLBACK_SYSTEM_PROMPT, MASTER_REASONING_PROMPT, MASTER_DECISION_PROMPT, EVALUATOR_REASONING_PROMPT, EVALUATOR_SCORING_PROMPT, FOLLOWUP_SYSTEM_PROMPT, REPORT_AGGREGATE_SYSTEM_PROMPT`，不包含 OPENING/BRIEFING/DECIDE 系列。

- [ ] **Step 3: 暂不 commit**，等 Task 3-4 一起。

---

## Task 3: 重写 nodes.py（清理 + 占位）

**Files:**
- Modify: `backend/app/agents/interviewer/nodes.py`

本任务只做清理 + 把要新增的节点写成最小占位（NotImplementedError）；真正实现放到 Task 6-11。

- [ ] **Step 1: 用以下内容替换整个 nodes.py 文件**

```python
"""Node functions for the multi-agent interviewer LangGraph."""
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.agents.interviewer.prompts import (
    CLOSING_SYSTEM_PROMPT,
    FOLLOWUP_SYSTEM_PROMPT,
    QUESTION_SYSTEM_PROMPT,
    REPORT_AGGREGATE_SYSTEM_PROMPT,
    REPORT_FALLBACK_SYSTEM_PROMPT,
)
from app.agents.interviewer.state import InterviewState, TurnEvaluation
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.agents-1.interviewer.nodes")


# ─────────────────────────────────────────────
# 模型与工具
# ─────────────────────────────────────────────

def _chat_model(*, fast: bool = False, streaming: bool = False) -> ChatOpenAI:
    """构造一次 LLM 客户端。fast=True 用于 master 等延迟敏感节点。"""
    settings = get_settings()
    model_name = settings.openai_model_chat_fast if fast else settings.openai_model_chat
    return ChatOpenAI(
        model=model_name,
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
        streaming=streaming,
    )


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


def _state_messages(state: InterviewState) -> list[BaseMessage]:
    """注入背景信息系统消息。"""
    messages = state.get("messages", [])
    context_parts: list[str] = []
    if state.get("target_role"):
        context_parts.append(f"目标岗位：{state['target_role']}")
    if state.get("target_company"):
        context_parts.append(f"目标公司：{state['target_company']}")
    if state.get("user_background"):
        context_parts.append(f"项目背景/技术主题：{state['user_background']}")
    q_count = state.get("question_count", 0)
    q_total = state.get("total_questions", 5)
    if q_count > 0:
        context_parts.append(f"当前进度：第 {q_count} 题 / 共 {q_total} 题")
    if not context_parts:
        return messages
    summary = "【当前已确定的面试背景信息】：\n" + "\n".join(context_parts)
    return [SystemMessage(content=summary)] + messages


async def _generate_text(system_prompt: str, state: InterviewState) -> str:
    chunks: list[str] = []
    model = _chat_model().with_config(tags=["interviewer_answer_stream"])
    messages = _state_messages(state) + [SystemMessage(content=system_prompt)]
    async for chunk in model.astream(messages):
        chunks.append(_content_to_text(chunk.content))
    return "".join(chunks).strip()


# ─────────────────────────────────────────────
# 节点函数
# ─────────────────────────────────────────────

async def load_context_node(state: InterviewState) -> InterviewState:
    """Normalize defaults before master scheduling."""
    return {
        "stage": state.get("stage") or "interview",
        "question_count": state.get("question_count", 0),
        "total_questions": state.get("total_questions", 5),
        "followup_count": state.get("followup_count", 0),
        "max_followups": state.get("max_followups", 2),
        "turn_evaluations": state.get("turn_evaluations", []),
    }


async def _master_phase1_stream(context: str) -> None:
    """Task 8 实装。占位是为了让 Task 7 的测试能 patch 这个符号。"""
    raise NotImplementedError("_master_phase1_stream is implemented in Task 8")


async def _master_phase2_decide(context: str):
    """Task 8 实装。"""
    raise NotImplementedError("_master_phase2_decide is implemented in Task 8")


async def master_node(state: InterviewState) -> InterviewState:
    """Phase 3+ 真·动态调度。Task 8 实现。"""
    raise NotImplementedError("master_node is implemented in Task 8")


async def _evaluator_reason_stream(context: str) -> None:
    """Task 9 实装。"""
    raise NotImplementedError("_evaluator_reason_stream is implemented in Task 9")


async def _evaluator_score(context: str):
    """Task 9 实装。"""
    raise NotImplementedError("_evaluator_score is implemented in Task 9")


async def evaluator_node(state: InterviewState) -> InterviewState:
    """每轮 4 维度评分。Task 9 实现。"""
    raise NotImplementedError("evaluator_node is implemented in Task 9")


async def _report_aggregate_text(state: InterviewState, dim_avg: dict[str, float]):
    """Task 10 实装。"""
    raise NotImplementedError("_report_aggregate_text is implemented in Task 10")


async def _report_fallback_full_eval(state: InterviewState):
    """Task 10 实装。"""
    raise NotImplementedError("_report_fallback_full_eval is implemented in Task 10")


async def generate_prepared_question_reply(question_text: str, state: InterviewState) -> str:
    system_prompt = (
        f"你是候选人的模拟面试官。请用温和、专业、自然的面试官口吻，向候选人提出以下指定的问题。"
        f"可以有一句简短的过渡或开场词，然后直接、清晰地提出问题，不要有多余的废话或总结。"
        f"指定提出的问题：{question_text}"
    )
    return await _generate_text(system_prompt, state)


async def ask_question_node(state: InterviewState) -> InterviewState:
    """出新一题（优先用 prepared_questions）。"""
    next_question_count = state.get("question_count", 0) + 1
    prepared = state.get("prepared_questions") or []
    idx = state.get("current_question_index", 0)

    if prepared and idx < len(prepared):
        question_text = prepared[idx]["question"]
        assistant_message = await generate_prepared_question_reply(
            question_text, {**state, "question_count": next_question_count}
        )
        return {
            "stage": "interview",
            "question_count": next_question_count,
            "followup_count": 0,
            "current_question_index": idx + 1,
            "assistant_message": assistant_message,
        }

    return {
        "stage": "interview",
        "question_count": next_question_count,
        "followup_count": 0,
        "assistant_message": await _generate_text(
            QUESTION_SYSTEM_PROMPT, {**state, "question_count": next_question_count}
        ),
    }


async def followup_node(state: InterviewState) -> InterviewState:
    """流式生成追问（不再依赖 decide_next 输出的 followup_question）。"""
    text = await _generate_text(FOLLOWUP_SYSTEM_PROMPT, state)
    return {
        "stage": "interview",
        "followup_count": state.get("followup_count", 0) + 1,
        "assistant_message": text,
    }


async def closing_node(state: InterviewState) -> InterviewState:
    return {
        "stage": "closing",
        "assistant_message": await _generate_text(CLOSING_SYSTEM_PROMPT, state),
    }


class ReportOutput(BaseModel):
    overall_score: float
    technical_depth: float
    quantified_results: float
    failure_tradeoffs: float
    structure: float
    highlights: list[str]
    improvements: list[str]
    key_concepts: list[str]
    common_mistakes: list[str]


async def report_node(state: InterviewState) -> InterviewState:
    """聚合 turn_evaluations 出最终报告。Task 11 实现。"""
    raise NotImplementedError("report_node aggregation is implemented in Task 11")
```

- [ ] **Step 2: 跑 import 检查**

```bash
cd backend && .venv/bin/python -c "from app.agents.interviewer import nodes; print('ok')"
```

Expected: 输出 `ok`，无 ImportError。

---

## Task 4: 重写 graph.py（chain 路由占位）

**Files:**
- Modify: `backend/app/agents/interviewer/graph.py`

本任务搭好 graph 拓扑骨架；真正的 chain 路由依赖于 Task 8 实装的 master_node。

- [ ] **Step 1: 用以下内容替换整个 graph.py 文件**

```python
"""LangGraph definition for the multi-agent interviewer."""
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from app.agents.interviewer import nodes
from app.agents.interviewer.state import InterviewState

_interviewer_graph: Any | None = None
_checkpoint_stack: AsyncExitStack | None = None


def _to_psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


CHAIN_NODES = {"evaluator", "followup", "ask_question", "closing"}


def route_after_master(state: InterviewState) -> str:
    chain = state.get("chain") or []
    if not chain:
        return "followup"  # 防御性 fallback
    head = chain[0]
    if head not in CHAIN_NODES:
        return "followup"
    return head


def _route_next_in_chain(current: str):
    def _route(state: InterviewState) -> str:
        chain = state.get("chain") or []
        try:
            idx = chain.index(current)
        except ValueError:
            return END
        if idx + 1 >= len(chain):
            return END
        return chain[idx + 1]
    return _route


def build_interviewer_graph(checkpointer: Any | None = None):
    graph = StateGraph(InterviewState)
    graph.add_node("load_context", nodes.load_context_node)
    graph.add_node("master", nodes.master_node)
    graph.add_node("evaluator", nodes.evaluator_node)
    graph.add_node("ask_question", nodes.ask_question_node)
    graph.add_node("followup", nodes.followup_node)
    graph.add_node("closing", nodes.closing_node)
    graph.add_node("report", nodes.report_node)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "master")

    graph.add_conditional_edges(
        "master",
        route_after_master,
        {
            "evaluator": "evaluator",
            "followup": "followup",
            "ask_question": "ask_question",
            "closing": "closing",
        },
    )

    # evaluator 后看 chain 下一个
    graph.add_conditional_edges(
        "evaluator",
        _route_next_in_chain("evaluator"),
        {
            "followup": "followup",
            "ask_question": "ask_question",
            "closing": "closing",
            END: END,
        },
    )

    graph.add_edge("ask_question", END)
    graph.add_edge("followup", END)
    graph.add_edge("closing", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)


def get_interviewer_graph():
    global _interviewer_graph
    if _interviewer_graph is None:
        _interviewer_graph = build_interviewer_graph()
    return _interviewer_graph


async def setup_interviewer_checkpointer(database_url: str) -> None:
    global _checkpoint_stack, _interviewer_graph
    if _checkpoint_stack is not None:
        await _checkpoint_stack.aclose()

    stack = AsyncExitStack()
    checkpointer = await stack.enter_async_context(
        AsyncPostgresSaver.from_conn_string(_to_psycopg_url(database_url))
    )
    await checkpointer.setup()
    _checkpoint_stack = stack
    _interviewer_graph = build_interviewer_graph(checkpointer=checkpointer)


async def close_interviewer_checkpointer() -> None:
    global _checkpoint_stack, _interviewer_graph
    if _checkpoint_stack is not None:
        await _checkpoint_stack.aclose()
        _checkpoint_stack = None
    _interviewer_graph = build_interviewer_graph()


async def run_interviewer_turn(state: InterviewState) -> InterviewState:
    thread_id = state["session_id"]
    return await get_interviewer_graph().ainvoke(
        state,
        config={"configurable": {"thread_id": thread_id}},
    )


# stream_interviewer_turn_events 在 Task 13 重写
async def stream_interviewer_turn_events(state: InterviewState) -> AsyncIterator[dict[str, Any]]:
    raise NotImplementedError("stream_interviewer_turn_events rewritten in Task 13")
```

- [ ] **Step 2: 跑 import 检查**

```bash
cd backend && .venv/bin/python -c "from app.agents.interviewer import graph; print('ok')"
```

Expected: `ok`。

- [ ] **Step 3: 跑 lint 看新文件没有 ruff 报错**

```bash
cd backend && .venv/bin/python -m ruff check app/agents-1/interviewer/
```

Expected: 无错误。

---

## Task 5: 删除旧测试，先让 CI 绿一次

**Files:**
- Modify: `backend/tests/unit/test_interviewer_graph.py`

- [ ] **Step 1: 打开 `test_interviewer_graph.py` 查看现有用例**

```bash
cd backend && grep -n "^def test_\|^async def test_" tests/unit/test_interviewer_graph.py
```

记录现有用例名。

- [ ] **Step 2: 删除所有涉及 opening/briefing/decide_next 的测试**

策略：用编辑器或 `sed` 把整个测试文件清空，只保留：
- `test_route_after_load_with_prepared_questions`（如果存在，验证 prepared_questions 优先；但因为 graph 拓扑已变，路由名也变了，**直接删除整个文件内容，替换为占位测试**）

用以下内容**整体替换** `test_interviewer_graph.py`：

```python
"""interviewer graph 重构后的占位测试。详细 chain 路由测试见 test_interviewer_chain_routing.py。"""
import pytest

from app.agents.interviewer.graph import (
    CHAIN_NODES,
    build_interviewer_graph,
    route_after_master,
)


def test_chain_nodes_exposes_master_subagents():
    """master 子 agent 池必须是 evaluator/followup/ask_question/closing 四者。"""
    assert CHAIN_NODES == {"evaluator", "followup", "ask_question", "closing"}


def test_route_after_master_empty_chain_fallback_to_followup():
    """空 chain 防御性 fallback。"""
    assert route_after_master({"chain": []}) == "followup"
    assert route_after_master({}) == "followup"


def test_route_after_master_uses_chain_head():
    assert route_after_master({"chain": ["evaluator", "followup"]}) == "evaluator"
    assert route_after_master({"chain": ["closing"]}) == "closing"


def test_route_after_master_unknown_node_falls_back_to_followup():
    assert route_after_master({"chain": ["nonexistent"]}) == "followup"


def test_build_interviewer_graph_does_not_error():
    """graph 编译本身不应抛错。"""
    g = build_interviewer_graph()
    assert g is not None
```

- [ ] **Step 3: 跑测试确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_graph.py -v
```

Expected: 5 个测试全部 PASS。

- [ ] **Step 4: 跑全量 lint + typecheck**

```bash
cd backend && .venv/bin/python -m ruff check app/agents-1/interviewer/ && .venv/bin/python -m mypy app/agents-1/interviewer
```

Expected: 无错误。

- [ ] **Step 5: Commit Batch A**

```bash
git add backend/app/agents-1/interviewer/state.py backend/app/agents-1/interviewer/prompts.py backend/app/agents-1/interviewer/nodes.py backend/app/agents-1/interviewer/graph.py backend/tests/unit/test_interviewer_graph.py
git commit -m "refactor(interviewer): remove opening/briefing/decide_next, scaffold master chain routing"
```

---

# Batch B · 后端核心节点实装

## Task 6: settings 增加 fast 模型配置

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 读取 config.py 找到 Settings 类内 openai_model_chat 字段**

```bash
cd backend && grep -n "openai_model_chat" app/core/config.py
```

- [ ] **Step 2: 在 `openai_model_chat` 字段附近追加 `openai_model_chat_fast`**

定位到 `openai_model_chat: str = ...` 那一行，紧随其后追加：

```python
    openai_model_chat_fast: str = "claude-haiku-4-5-20251001"
```

（如果项目用 OpenAI gpt-4.1-mini 等可读取 settings 实际值；这里给一个合理默认，可以被 env 覆盖。）

- [ ] **Step 3: 跑 config 测试**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_config.py -v
```

Expected: 现有用例全 PASS（新增字段有默认值，不破坏现有测试）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/config.py
git commit -m "chore(config): add openai_model_chat_fast for master node"
```

---

## Task 7: 写 master_node 的失败测试

**Files:**
- Create: `backend/tests/unit/test_interviewer_master_node.py`

- [ ] **Step 1: 写完整测试文件**

```python
"""master_node 单元测试：chain 决策 + 合法性约束 + 流式 bullet。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.interviewer.nodes import master_node


@pytest.mark.asyncio
async def test_master_first_turn_forces_ask_question():
    """question_count == 0：强制 chain = ['ask_question']，即使 LLM 输出别的。"""
    fake_decision = MagicMock(chain=["evaluator", "followup"], reason="LLM 的随意输出")
    state = {"question_count": 0, "messages": []}
    with patch("app.agents-1.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["ask_question"]


@pytest.mark.asyncio
async def test_master_exhausted_forces_closing():
    """题数耗尽且追问耗尽：强制 chain = ['closing']。"""
    fake_decision = MagicMock(chain=["evaluator", "followup"], reason="")
    state = {
        "question_count": 5,
        "total_questions": 5,
        "followup_count": 2,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents-1.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["closing"]


@pytest.mark.asyncio
async def test_master_normal_chain_passes_through():
    """中段轮次：LLM 的 chain 不被覆盖。"""
    fake_decision = MagicMock(chain=["evaluator", "followup"], reason="OK")
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents-1.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["evaluator", "followup"]


@pytest.mark.asyncio
async def test_master_strips_after_closing():
    """chain 含 closing 时，closing 之后的节点被丢弃。"""
    fake_decision = MagicMock(chain=["closing", "ask_question"], reason="")
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents-1.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["closing"]


@pytest.mark.asyncio
async def test_master_appends_followup_when_tail_is_evaluator():
    """末尾是 evaluator（非合法终态）时，追加 followup。"""
    fake_decision = MagicMock(chain=["evaluator"], reason="")
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents-1.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"][-1] in {"followup", "ask_question", "closing"}
    assert result["chain"] == ["evaluator", "followup"]


@pytest.mark.asyncio
async def test_master_phase2_failure_falls_back():
    """Phase 2 抛错：fallback chain。"""
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents-1.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._master_phase2_decide", new=AsyncMock(side_effect=RuntimeError("LLM down"))):
        result = await master_node(state)
    assert result["chain"] == ["evaluator", "followup"]


@pytest.mark.asyncio
async def test_master_empty_chain_falls_back():
    fake_decision = MagicMock(chain=[], reason="")
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents-1.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["evaluator", "followup"]
```

- [ ] **Step 2: 跑测试确认全部失败（master_node 还是 NotImplementedError）**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_master_node.py -v
```

Expected: 7 个测试全部 FAIL（NotImplementedError）。

---

## Task 8: 实现 master_node

**Files:**
- Modify: `backend/app/agents/interviewer/nodes.py`

- [ ] **Step 1: 在 nodes.py 顶部 import 区追加 master 所需依赖**

定位到 `from app.agents.interviewer.prompts import (` 这块，扩充为：

```python
from app.agents.interviewer.prompts import (
    CLOSING_SYSTEM_PROMPT,
    EVALUATOR_REASONING_PROMPT,
    EVALUATOR_SCORING_PROMPT,
    FOLLOWUP_SYSTEM_PROMPT,
    MASTER_DECISION_PROMPT,
    MASTER_REASONING_PROMPT,
    QUESTION_SYSTEM_PROMPT,
    REPORT_AGGREGATE_SYSTEM_PROMPT,
    REPORT_FALLBACK_SYSTEM_PROMPT,
)
```

并在文件靠近 imports 区追加 retry 装饰器（复用 prepare 的模式）：

```python
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_RETRYABLE = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)

_retry_llm = retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    reraise=True,
)
```

- [ ] **Step 2: 实装 master_node + 两个 helper**

把原来的 `async def master_node` 占位**替换为**：

```python
class _InterviewMasterDecision(BaseModel):
    chain: list[str] = []
    reason: str = ""


VALID_CHAIN_NODES = {"evaluator", "followup", "ask_question", "closing"}
TERMINAL_NODES = {"followup", "ask_question", "closing"}
DEFAULT_FALLBACK_CHAIN = ["evaluator", "followup"]


def _build_master_context(state: InterviewState) -> str:
    parts: list[str] = []
    parts.append(f"题目进度：{state.get('question_count', 0)} / {state.get('total_questions', 5)}")
    parts.append(f"当题追问次数：{state.get('followup_count', 0)} / {state.get('max_followups', 2)}")
    if state.get("target_role"):
        parts.append(f"目标岗位：{state['target_role']}")
    last_user_msg = ""
    for m in reversed(state.get("messages", [])):
        if getattr(m, "type", "") == "human":
            last_user_msg = str(getattr(m, "content", ""))
            break
    if last_user_msg:
        snippet = last_user_msg[:200]
        parts.append(f"候选人最新回答（节选）：{snippet}")
    return "\n".join(parts)


async def _master_phase1_stream(context: str) -> None:
    """Phase 1：流式输出推理 bullet。tag 让 SSE 层捕获。"""
    model = _chat_model(fast=True, streaming=True).with_config(tags=["master_token_stream"])
    prompt = MASTER_REASONING_PROMPT.format(context=context)
    async for _ in model.astream([SystemMessage(content=prompt)]):
        pass


@_retry_llm
async def _master_phase2_decide(context: str) -> _InterviewMasterDecision:
    """Phase 2：结构化输出 chain。"""
    model = _chat_model(fast=True).with_structured_output(_InterviewMasterDecision)
    prompt = MASTER_DECISION_PROMPT.format(context=context)
    out = await model.ainvoke([SystemMessage(content=prompt)])
    if isinstance(out, _InterviewMasterDecision):
        return out
    return _InterviewMasterDecision(chain=[], reason="非预期输出")


def _enforce_chain(chain: list[str], state: InterviewState) -> list[str]:
    """按 spec §6.2 五条合法性约束修正 chain。"""
    question_count = state.get("question_count", 0)
    total_questions = state.get("total_questions", 5)
    followup_count = state.get("followup_count", 0)
    max_followups = state.get("max_followups", 2)

    # 1. 首轮强制 ask_question
    if question_count == 0:
        if chain != ["ask_question"]:
            log.warning("master_chain_forced_first_turn", original=chain)
        return ["ask_question"]

    # 2. 题数 + 追问都耗尽强制 closing
    if question_count >= total_questions and followup_count >= max_followups:
        if chain != ["closing"]:
            log.warning("master_chain_forced_closing", original=chain)
        return ["closing"]

    # 3. 过滤非法节点 + 去空
    cleaned = [n for n in chain if n in VALID_CHAIN_NODES]
    if not cleaned:
        log.warning("master_chain_empty_fallback", original=chain)
        cleaned = list(DEFAULT_FALLBACK_CHAIN)

    # 4. closing 后的节点丢弃
    if "closing" in cleaned:
        idx = cleaned.index("closing")
        cleaned = cleaned[: idx + 1]

    # 5. 末尾必须是终态节点
    if cleaned[-1] not in TERMINAL_NODES:
        log.warning("master_chain_tail_invalid", original=chain, fixed=cleaned)
        cleaned.append("followup")

    return cleaned


async def master_node(state: InterviewState) -> InterviewState:
    """Phase 3+ 真·动态调度：LLM 决定 chain。"""
    context = _build_master_context(state)

    try:
        await _master_phase1_stream(context)
    except Exception as exc:
        log.warning("master_phase1_failed", error=str(exc))

    try:
        decision = await _master_phase2_decide(context)
        chain = list(decision.chain)
        reason = decision.reason
    except Exception as exc:
        log.error("master_phase2_failed", error=str(exc))
        chain = []
        reason = "Phase 2 fallback"

    final_chain = _enforce_chain(chain, state)

    log.info("master_done", chain=final_chain, reason=reason)
    return {
        **state,
        "chain": final_chain,
        "master_reason": reason,
    }
```

- [ ] **Step 3: 跑 master 测试确认全 PASS**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_master_node.py -v
```

Expected: 7 个测试全 PASS。

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents-1/interviewer/nodes.py backend/tests/unit/test_interviewer_master_node.py
git commit -m "feat(interviewer): implement master_node with chain decision and enforcement"
```

---

## Task 9: 写 evaluator_node 测试并实装

**Files:**
- Create: `backend/tests/unit/test_interviewer_evaluator_node.py`
- Modify: `backend/app/agents/interviewer/nodes.py`

- [ ] **Step 1: 写测试**

```python
"""evaluator_node 单元测试：写入 turn_evaluations + 失败降级。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.interviewer.nodes import evaluator_node


@pytest.mark.asyncio
async def test_evaluator_writes_turn_evaluation_into_state():
    fake_scoring = MagicMock(
        bullets=["覆盖 CAP", "缺量化指标"],
        technical_depth=7.0,
        quantified_results=4.0,
        failure_tradeoffs=6.0,
        structure=7.5,
        summary_score=6.1,
    )
    state = {
        "question_count": 2,
        "followup_count": 0,
        "current_question_index": 2,
        "turn_evaluations": [],
        "messages": [HumanMessage(content="我会用 CAP 解决"), AIMessage(content="...")],
    }
    with patch("app.agents-1.interviewer.nodes._evaluator_reason_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._evaluator_score", new=AsyncMock(return_value=fake_scoring)):
        result = await evaluator_node(state)
    evals = result["turn_evaluations"]
    assert len(evals) == 1
    assert evals[0]["technical_depth"] == 7.0
    assert evals[0]["summary_score"] == 6.1
    assert evals[0]["bullets"] == ["覆盖 CAP", "缺量化指标"]
    assert evals[0]["question_index"] == 2


@pytest.mark.asyncio
async def test_evaluator_failure_passthrough_without_writing():
    """LLM 失败时不写 turn_evaluations，但不抛错（保证主链路继续）。"""
    state = {
        "question_count": 2,
        "followup_count": 0,
        "current_question_index": 2,
        "turn_evaluations": [],
        "messages": [],
    }
    with patch("app.agents-1.interviewer.nodes._evaluator_reason_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._evaluator_score", new=AsyncMock(side_effect=RuntimeError("down"))):
        result = await evaluator_node(state)
    assert result["turn_evaluations"] == []


@pytest.mark.asyncio
async def test_evaluator_appends_not_overwrites():
    existing = [{"question_index": 1, "summary_score": 7.0, "bullets": []}]
    fake_scoring = MagicMock(
        bullets=["b1"],
        technical_depth=8.0,
        quantified_results=8.0,
        failure_tradeoffs=8.0,
        structure=8.0,
        summary_score=8.0,
    )
    state = {
        "question_count": 2,
        "followup_count": 1,
        "current_question_index": 2,
        "turn_evaluations": existing,
        "messages": [],
    }
    with patch("app.agents-1.interviewer.nodes._evaluator_reason_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents-1.interviewer.nodes._evaluator_score", new=AsyncMock(return_value=fake_scoring)):
        result = await evaluator_node(state)
    assert len(result["turn_evaluations"]) == 2
    assert result["turn_evaluations"][0]["summary_score"] == 7.0
```

- [ ] **Step 2: 跑测试预期 FAIL**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_evaluator_node.py -v
```

Expected: 全 FAIL（NotImplementedError）。

- [ ] **Step 3: 实装 evaluator_node**

在 nodes.py 找到 `async def evaluator_node` 占位，**替换为**：

```python
class _EvaluatorScoring(BaseModel):
    bullets: list[str] = []
    technical_depth: float = 5.0
    quantified_results: float = 5.0
    failure_tradeoffs: float = 5.0
    structure: float = 5.0
    summary_score: float = 5.0


def _build_evaluator_context(state: InterviewState) -> str:
    parts: list[str] = []
    if state.get("target_role"):
        parts.append(f"目标岗位：{state['target_role']}")
    # 最近一题（问题文本）+ 最近一句用户回答
    last_user = ""
    last_ai = ""
    for m in reversed(state.get("messages", [])):
        if not last_user and getattr(m, "type", "") == "human":
            last_user = str(getattr(m, "content", ""))[:600]
        elif not last_ai and getattr(m, "type", "") == ".ai":
            last_ai = str(getattr(m, "content", ""))[:300]
        if last_user and last_ai:
            break
    if last_ai:
        parts.append(f"面试官刚问的：{last_ai}")
    if last_user:
        parts.append(f"候选人回答：{last_user}")
    return "\n".join(parts)


async def _evaluator_reason_stream(context: str) -> None:
    model = _chat_model(streaming=True).with_config(tags=["evaluator_token_stream"])
    prompt = EVALUATOR_REASONING_PROMPT.format(context=context)
    async for _ in model.astream([SystemMessage(content=prompt)]):
        pass


@_retry_llm
async def _evaluator_score(context: str) -> _EvaluatorScoring:
    model = _chat_model().with_structured_output(_EvaluatorScoring)
    prompt = EVALUATOR_SCORING_PROMPT.format(context=context)
    out = await model.ainvoke([SystemMessage(content=prompt)])
    if isinstance(out, _EvaluatorScoring):
        return out
    return _EvaluatorScoring()


async def evaluator_node(state: InterviewState) -> InterviewState:
    context = _build_evaluator_context(state)
    try:
        await _evaluator_reason_stream(context)
    except Exception as exc:
        log.warning("evaluator_reason_failed", error=str(exc))

    try:
        scoring = await _evaluator_score(context)
    except Exception as exc:
        log.error("evaluator_score_failed", error=str(exc))
        return {**state, "turn_evaluations": list(state.get("turn_evaluations", []))}

    entry: TurnEvaluation = {
        "question_index": state.get("current_question_index", state.get("question_count", 0)),
        "followup_index": state.get("followup_count", 0),
        "bullets": list(scoring.bullets),
        "technical_depth": scoring.technical_depth,
        "quantified_results": scoring.quantified_results,
        "failure_tradeoffs": scoring.failure_tradeoffs,
        "structure": scoring.structure,
        "summary_score": scoring.summary_score,
    }
    updated = list(state.get("turn_evaluations", []))
    updated.append(entry)
    log.info("evaluator_done", summary_score=scoring.summary_score)
    return {**state, "turn_evaluations": updated}
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_evaluator_node.py -v
```

Expected: 3 个测试全 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents-1/interviewer/nodes.py backend/tests/unit/test_interviewer_evaluator_node.py
git commit -m "feat(interviewer): implement evaluator_node with 4-dimension scoring"
```

---

## Task 10: 改造 report_node 聚合 turn_evaluations

**Files:**
- Create: `backend/tests/unit/test_interviewer_report_aggregate.py`
- Modify: `backend/app/agents/interviewer/nodes.py`

- [ ] **Step 1: 写测试**

```python
"""report_node 聚合 turn_evaluations 测试。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.interviewer.nodes import report_node


@pytest.mark.asyncio
async def test_report_averages_turn_evaluations():
    """两轮评估：四维取均值，overall = 各维均值。"""
    state = {
        "messages": [],
        "turn_evaluations": [
            {
                "question_index": 1, "followup_index": 0, "bullets": ["a"],
                "technical_depth": 6.0, "quantified_results": 4.0,
                "failure_tradeoffs": 7.0, "structure": 5.0, "summary_score": 5.5,
            },
            {
                "question_index": 2, "followup_index": 0, "bullets": ["b"],
                "technical_depth": 8.0, "quantified_results": 8.0,
                "failure_tradeoffs": 7.0, "structure": 9.0, "summary_score": 8.0,
            },
        ],
    }
    fake_text = MagicMock(
        highlights=["亮点1"], improvements=["改进1"],
        key_concepts=["CAP"], common_mistakes=["缺指标"],
    )
    with patch("app.agents-1.interviewer.nodes._report_aggregate_text", new=AsyncMock(return_value=fake_text)):
        result = await report_node(state)
    report = result["report"]
    assert report["technical_depth"] == pytest.approx(7.0)
    assert report["quantified_results"] == pytest.approx(6.0)
    assert report["structure"] == pytest.approx(7.0)
    expected_overall = (7.0 + 6.0 + 7.0 + 7.0) / 4
    assert report["overall_score"] == pytest.approx(expected_overall, rel=0.01)
    assert report["highlights"] == ["亮点1"]


@pytest.mark.asyncio
async def test_report_empty_evaluations_uses_fallback():
    """无 turn_evaluations 时走 LLM 整场评估降级路径。"""
    fake_fallback = MagicMock(
        overall_score=6.5,
        technical_depth=6.0, quantified_results=5.0,
        failure_tradeoffs=7.0, structure=8.0,
        highlights=["h"], improvements=["i"],
        key_concepts=["k"], common_mistakes=["m"],
    )
    state = {"messages": [], "turn_evaluations": []}
    with patch("app.agents-1.interviewer.nodes._report_fallback_full_eval", new=AsyncMock(return_value=fake_fallback)):
        result = await report_node(state)
    report = result["report"]
    assert report["overall_score"] == 6.5
    assert report["technical_depth"] == 6.0


@pytest.mark.asyncio
async def test_report_text_failure_returns_empty_report():
    state = {
        "messages": [],
        "turn_evaluations": [{
            "question_index": 1, "followup_index": 0, "bullets": [],
            "technical_depth": 5.0, "quantified_results": 5.0,
            "failure_tradeoffs": 5.0, "structure": 5.0, "summary_score": 5.0,
        }],
    }
    with patch("app.agents-1.interviewer.nodes._report_aggregate_text", new=AsyncMock(side_effect=RuntimeError("LLM"))):
        result = await report_node(state)
    assert result["report"] == {}
```

- [ ] **Step 2: 跑测试 FAIL**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_report_aggregate.py -v
```

Expected: 3 个测试 FAIL（NotImplementedError）。

- [ ] **Step 3: 实装 report_node 与 helper**

在 nodes.py 中找到占位 `async def report_node`，**替换为**：

```python
class _ReportTextOutput(BaseModel):
    highlights: list[str] = []
    improvements: list[str] = []
    key_concepts: list[str] = []
    common_mistakes: list[str] = []


@_retry_llm
async def _report_aggregate_text(state: InterviewState, dim_avg: dict[str, float]) -> _ReportTextOutput:
    """已有 turn_evaluations：仅做文字归纳，不重新打分。"""
    bullet_lines: list[str] = []
    for ev in state.get("turn_evaluations", []):
        for b in ev.get("bullets", []):
            bullet_lines.append(f"- 第{ev.get('question_index', '?')}题: {b}")
    bullet_block = "\n".join(bullet_lines) if bullet_lines else "（无）"
    score_block = (
        f"维度平均：技术深度 {dim_avg['technical_depth']:.1f}，"
        f"量化 {dim_avg['quantified_results']:.1f}，"
        f"失败处理 {dim_avg['failure_tradeoffs']:.1f}，"
        f"结构 {dim_avg['structure']:.1f}"
    )
    context_msg = SystemMessage(
        content=f"{REPORT_AGGREGATE_SYSTEM_PROMPT}\n\n"
                f"【评分上下文】：\n{score_block}\n\n"
                f"【每轮要点摘要】：\n{bullet_block}"
    )
    model = _chat_model().with_structured_output(_ReportTextOutput)
    history = list(state.get("messages", []))
    out = await model.ainvoke([*history, context_msg])
    if isinstance(out, _ReportTextOutput):
        return out
    return _ReportTextOutput()


@_retry_llm
async def _report_fallback_full_eval(state: InterviewState) -> ReportOutput:
    model = _chat_model().with_structured_output(ReportOutput)
    out = await model.ainvoke(
        [*_state_messages(state), SystemMessage(content=REPORT_FALLBACK_SYSTEM_PROMPT)]
    )
    if isinstance(out, ReportOutput):
        return out
    return ReportOutput(
        overall_score=0.0,
        technical_depth=0.0, quantified_results=0.0,
        failure_tradeoffs=0.0, structure=0.0,
        highlights=[], improvements=[], key_concepts=[], common_mistakes=[],
    )


def _average_dimensions(evals: list[dict]) -> dict[str, float]:
    n = max(len(evals), 1)
    dims = ("technical_depth", "quantified_results", "failure_tradeoffs", "structure")
    return {d: sum(float(e.get(d, 0)) for e in evals) / n for d in dims}


async def report_node(state: InterviewState) -> InterviewState:
    evals = state.get("turn_evaluations", [])

    if not evals:
        log.warning("report_fallback_no_turn_evals")
        try:
            out = await _report_fallback_full_eval(state)
            return {"report": out.model_dump()}
        except Exception as exc:
            log.error("report_fallback_failed", error=str(exc))
            return {"report": {}}

    dim_avg = _average_dimensions(evals)
    overall = sum(dim_avg.values()) / 4

    try:
        text = await _report_aggregate_text(state, dim_avg)
    except Exception as exc:
        log.error("report_aggregate_text_failed", error=str(exc))
        return {"report": {}}

    report = {
        "overall_score": round(overall, 1),
        "technical_depth": round(dim_avg["technical_depth"], 1),
        "quantified_results": round(dim_avg["quantified_results"], 1),
        "failure_tradeoffs": round(dim_avg["failure_tradeoffs"], 1),
        "structure": round(dim_avg["structure"], 1),
        "highlights": list(text.highlights),
        "improvements": list(text.improvements),
        "key_concepts": list(text.key_concepts),
        "common_mistakes": list(text.common_mistakes),
        "turn_evaluations": list(evals),
    }
    return {"report": report}
```

- [ ] **Step 4: 跑测试 PASS**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_report_aggregate.py -v
```

Expected: 3 个全 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents-1/interviewer/nodes.py backend/tests/unit/test_interviewer_report_aggregate.py
git commit -m "feat(interviewer): aggregate turn_evaluations in report_node"
```

---

## Task 11: chain 路由集成测试

**Files:**
- Create: `backend/tests/unit/test_interviewer_chain_routing.py`

- [ ] **Step 1: 写测试**

```python
"""chain 路由集成测试：master 出 chain → 节点顺序执行 → END。

不真调 LLM，把 master/evaluator/followup/ask_question/closing 全 patch。
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.interviewer.graph import build_interviewer_graph


@pytest.mark.asyncio
async def test_chain_evaluator_then_followup():
    """chain = ['evaluator', 'followup']：两个节点依次跑，到 END。"""
    g = build_interviewer_graph()
    state = {
        "session_id": "s1",
        "messages": [],
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }

    with patch("app.agents-1.interviewer.nodes.master_node",
               new=AsyncMock(return_value={**state, "chain": ["evaluator", "followup"]})), \
         patch("app.agents-1.interviewer.nodes.evaluator_node",
               new=AsyncMock(return_value={"turn_evaluations": [{"summary_score": 7.0}]})), \
         patch("app.agents-1.interviewer.nodes.followup_node",
               new=AsyncMock(return_value={"assistant_message": "追问内容"})):
        out = await g.ainvoke(state)
    assert out.get("assistant_message") == "追问内容"


@pytest.mark.asyncio
async def test_chain_just_followup_skips_evaluator():
    """chain = ['followup']：evaluator 不应被调用。"""
    g = build_interviewer_graph()
    state = {
        "session_id": "s2",
        "messages": [],
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }

    eval_mock = AsyncMock(return_value={"turn_evaluations": []})
    with patch("app.agents-1.interviewer.nodes.master_node",
               new=AsyncMock(return_value={**state, "chain": ["followup"]})), \
         patch("app.agents-1.interviewer.nodes.evaluator_node", new=eval_mock), \
         patch("app.agents-1.interviewer.nodes.followup_node",
               new=AsyncMock(return_value={"assistant_message": "拉回主题"})):
        out = await g.ainvoke(state)
    eval_mock.assert_not_called()
    assert out["assistant_message"] == "拉回主题"


@pytest.mark.asyncio
async def test_chain_closing_triggers_report():
    """chain = ['closing']：closing_node 后接 report_node。"""
    g = build_interviewer_graph()
    state = {
        "session_id": "s3",
        "messages": [],
        "question_count": 5,
        "total_questions": 5,
        "followup_count": 2,
        "max_followups": 2,
    }

    with patch("app.agents-1.interviewer.nodes.master_node",
               new=AsyncMock(return_value={**state, "chain": ["closing"]})), \
         patch("app.agents-1.interviewer.nodes.closing_node",
               new=AsyncMock(return_value={"assistant_message": "结束语", "stage": "closing"})), \
         patch("app.agents-1.interviewer.nodes.report_node",
               new=AsyncMock(return_value={"report": {"overall_score": 7.4}})):
        out = await g.ainvoke(state)
    assert out["report"]["overall_score"] == 7.4
    assert out["stage"] == "closing"


@pytest.mark.asyncio
async def test_chain_evaluator_then_ask_question():
    """chain = ['evaluator', 'ask_question']：进入下一题。"""
    g = build_interviewer_graph()
    state = {
        "session_id": "s4",
        "messages": [],
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 1,
        "max_followups": 2,
    }

    with patch("app.agents-1.interviewer.nodes.master_node",
               new=AsyncMock(return_value={**state, "chain": ["evaluator", "ask_question"]})), \
         patch("app.agents-1.interviewer.nodes.evaluator_node",
               new=AsyncMock(return_value={"turn_evaluations": [{"summary_score": 8.5}]})), \
         patch("app.agents-1.interviewer.nodes.ask_question_node",
               new=AsyncMock(return_value={"assistant_message": "第2题..."})):
        out = await g.ainvoke(state)
    assert out["assistant_message"] == "第2题..."
```

- [ ] **Step 2: 跑测试 PASS**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_chain_routing.py -v
```

Expected: 4 个测试全 PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_interviewer_chain_routing.py
git commit -m "test(interviewer): chain routing integration tests across all branches"
```

---

# Batch C · 后端 SSE 改造

## Task 12: 重写 stream_interviewer_turn_events 发 node_* 事件

**Files:**
- Modify: `backend/app/agents/interviewer/graph.py`

- [ ] **Step 1: 把 `stream_interviewer_turn_events` 占位替换为完整实现**

定位到 graph.py 中 `async def stream_interviewer_turn_events` 占位，**替换为**：

```python
NODE_LABELS = {
    "master": "MASTER",
    "evaluator": "评估",
    "followup": "面试官 · 追问",
    "ask_question": "面试官 · 出题",
    "closing": "收尾",
}

# 不发 node_* 事件的内部节点（用户无需可见）
_HIDDEN_NODES = {"load_context", "report"}


def _stream_chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


import time as _time


async def stream_interviewer_turn_events(state: InterviewState) -> AsyncIterator[dict[str, Any]]:
    """发出 node_start / node_token / node_done / token / final 事件。"""
    thread_id = state["session_id"]
    final_state: InterviewState | None = None
    elapsed_tracker: dict[str, float] = {}
    current_node: str | None = None

    async for event in get_interviewer_graph().astream_events(
        state,
        config={"configurable": {"thread_id": thread_id}},
        version="v2",
    ):
        ev_name = event.get("event", "")
        ev_node = event.get("metadata", {}).get("langgraph_node", "")
        tags = event.get("tags", []) or []

        # 节点开始
        if (
            ev_name == "on_chain_start"
            and ev_node
            and ev_node not in _HIDDEN_NODES
            and ev_node != current_node
        ):
            current_node = ev_node
            elapsed_tracker[ev_node] = _time.time()
            yield {
                "event": "node_start",
                "data": {"node": ev_node, "label": NODE_LABELS.get(ev_node, ev_node)},
            }

        # Token 流：根据 tag 路由
        if ev_name == "on_chat_model_stream":
            text = _stream_chunk_text(event.get("data", {}).get("chunk"))
            if not text:
                continue
            if "interviewer_answer_stream" in tags:
                # 沿用现有 delta 通道供前端 onDelta 处理（不改名）
                yield {"event": "token", "data": {"text": text}}
                continue
            if "master_token_stream" in tags:
                yield {"event": "node_token", "data": {"node": "master", "text": text}}
                continue
            if "evaluator_token_stream" in tags:
                yield {"event": "node_token", "data": {"node": "evaluator", "text": text}}
                continue

        # 节点结束
        if ev_name == "on_chain_end" and ev_node and ev_node not in _HIDDEN_NODES:
            elapsed_ms = int((_time.time() - elapsed_tracker.get(ev_node, _time.time())) * 1000)
            node_state = event.get("data", {}).get("output") or {}
            payload: dict[str, Any] = {"node": ev_node, "elapsed_ms": elapsed_ms}
            if ev_node == "master":
                payload["chain"] = node_state.get("chain", [])
            if ev_node == "evaluator":
                evals = node_state.get("turn_evaluations") or []
                if evals:
                    payload["summary_score"] = evals[-1].get("summary_score")
            yield {"event": "node_done", "data": payload}

        # 全图结束
        if ev_name == "on_chain_end" and event.get("name") == "LangGraph":
            final_state = event.get("data", {}).get("output")

    if final_state is None:
        raise RuntimeError("interviewer graph did not produce final state")
    yield {"event": "final", "data": final_state}
```

- [ ] **Step 2: 跑 lint / typecheck**

```bash
cd backend && .venv/bin/python -m ruff check app/agents-1/interviewer/graph.py && .venv/bin/python -m mypy app/agents-1/interviewer/graph.py
```

Expected: 无错误。

- [ ] **Step 3: 跑已有 chain 路由测试确保没破**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interviewer_chain_routing.py -v
```

Expected: 4 个测试仍 PASS。

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents-1/interviewer/graph.py
git commit -m "feat(interviewer): emit node_start/node_token/node_done SSE events"
```

---

## Task 13: 改造 interview_turn service 透传新事件

**Files:**
- Modify: `backend/app/services/interview_turn.py`

- [ ] **Step 1: 定位 `stream_interview_turn` 中处理 graph_event 的代码块**

```bash
cd backend && grep -n "graph_event\[" app/services/interview_turn.py
```

定位现有逻辑：仅处理 `token / final` 两种事件。

- [ ] **Step 2: 扩展事件处理**

把 `async for graph_event in stream_interviewer_turn_events(state):` 这个循环体替换为：

```python
    async for graph_event in stream_interviewer_turn_events(state):
        evt = graph_event["event"]
        data = graph_event["data"]
        if evt == "token":
            text = data.get("text", "")
            if text:
                assistant_chunks.append(text)
                yield {"event": "delta", "data": {"text": text}}
            continue
        if evt in ("node_start", "node_token", "node_done"):
            yield {"event": evt, "data": data}
            continue
        if evt == "final":
            output = data
```

- [ ] **Step 3: 跑既有集成测试**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_interview_turn_service.py -v
```

Expected: 既有用例可能因为 SSE 事件结构变化而失败；这些测试将在 Task 14 一起更新。先记录哪些 FAIL，不阻塞继续。

- [ ] **Step 4: Commit（即使现有测试还红）**

```bash
git add backend/app/services/interview_turn.py
git commit -m "feat(interview): pipe node_* SSE events from graph to API layer"
```

---

## Task 14: 集成测试 /api/v1/interview/turn 新事件流

**Files:**
- Modify: `backend/tests/integration/test_interview_turn_service.py`

- [ ] **Step 1: 打开测试文件查现状**

```bash
cd backend && grep -n "^async def test_\|^def test_" tests/integration/test_interview_turn_service.py | head -30
```

- [ ] **Step 2: 替换/追加测试覆盖新事件**

在文件末尾追加：

```python
@pytest.mark.asyncio
async def test_stream_interview_turn_emits_node_events(monkeypatch, db_session, test_user_id):
    """一次 turn 应包含 node_start / node_done / delta 序列。"""
    from app.services.interview_turn import stream_interview_turn

    async def fake_graph_events(state):
        yield {"event": "node_start", "data": {"node": "master", "label": "MASTER"}}
        yield {"event": "node_token", "data": {"node": "master", "text": "推理 bullet"}}
        yield {"event": "node_done", "data": {"node": "master", "elapsed_ms": 100, "chain": ["evaluator", "followup"]}}
        yield {"event": "node_start", "data": {"node": "evaluator", "label": "评估"}}
        yield {"event": "node_done", "data": {"node": "evaluator", "elapsed_ms": 200, "summary_score": 7.0}}
        yield {"event": "node_start", "data": {"node": "followup", "label": "面试官 · 追问"}}
        yield {"event": "token", "data": {"text": "你的故障"}}
        yield {"event": "token", "data": {"text": "恢复方案是什么？"}}
        yield {"event": "node_done", "data": {"node": "followup", "elapsed_ms": 800}}
        yield {"event": "final", "data": {
            "stage": "interview",
            "question_count": 1,
            "total_questions": 5,
            "followup_count": 1,
            "target_role": "test",
            "assistant_message": "你的故障恢复方案是什么？",
            "turn_evaluations": [{"summary_score": 7.0}],
        }}

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events",
        fake_graph_events,
    )

    events = []
    async for ev in stream_interview_turn(
        message="我回答完了",
        user_id=test_user_id,
        db=db_session,
    ):
        events.append(ev["event"])

    assert "node_start" in events
    assert "node_token" in events
    assert "node_done" in events
    assert "delta" in events
    assert "done" in events
```

- [ ] **Step 3: 跑测试**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_interview_turn_service.py::test_stream_interview_turn_emits_node_events -v
```

Expected: PASS。如果其他既有测试因为业务逻辑变化（如 stage 字段语义）失败，按需修正。

- [ ] **Step 4: 跑全量 backend 测试**

```bash
cd backend && .venv/bin/python -m pytest tests/ -v
```

Expected: 失败的测试只剩与 opening/briefing 旧流程有关、确实需要删除/更新的。逐一定位并修正。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/test_interview_turn_service.py
git commit -m "test(interview): cover node_* SSE events end-to-end through service layer"
```

---

# Batch D · 前端契约

## Task 15: 抽 trace 共享类型到 prepare-types.ts

**Files:**
- Modify: `frontend/lib/prepare-types.ts`
- Modify: `frontend/app/interview/_components/trace-node.tsx`
- Modify: `frontend/app/interview/_components/agent-trace.tsx`

- [ ] **Step 1: 打开 trace-node.tsx 找到 TraceNodeStatus 定义**

```bash
grep -n "TraceNodeStatus" frontend/app/interview/_components/trace-node.tsx
```

- [ ] **Step 2: 在 prepare-types.ts 文末追加共享类型**

打开 `frontend/lib/prepare-types.ts`，在末尾追加：

```ts
export type TraceNodeStatus = "pending" | "running" | "done";

export interface TraceNodeData {
  id: string;
  label: string;
  title?: string;
  status: TraceNodeStatus;
  tokens: string;
  elapsedMs?: number;
}
```

- [ ] **Step 3: 改 trace-node.tsx 从 prepare-types 导入 TraceNodeStatus**

定位到 trace-node.tsx 中：
```ts
export type TraceNodeStatus = "pending" | "running" | "done";
```
**替换为**：
```ts
import type { TraceNodeStatus } from "@/lib/prepare-types";
export type { TraceNodeStatus };  // 保留 re-export 防止其他文件断链
```

- [ ] **Step 4: 改 agent-trace.tsx 从 prepare-types 导入 TraceNodeData**

定位 agent-trace.tsx 中：
```ts
export type TraceNodeData = { ... };
```
**替换为**：
```ts
import type { TraceNodeData } from "@/lib/prepare-types";
export type { TraceNodeData };
```

- [ ] **Step 5: 跑前端 typecheck**

```bash
cd frontend && pnpm typecheck
```

Expected: 无错误。

- [ ] **Step 6: 跑现有测试**

```bash
cd frontend && pnpm test -- preparation-card trace-node
```

Expected: 现有 trace-node / preparation-card 测试都 PASS。

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/prepare-types.ts frontend/app/interview/_components/trace-node.tsx frontend/app/interview/_components/agent-trace.tsx
git commit -m "refactor(frontend): centralize TraceNodeStatus and TraceNodeData in prepare-types"
```

---

## Task 16: streamInterviewChat 添加 onTraceNode 回调

**Files:**
- Modify: `frontend/lib/interview-chat.ts`

- [ ] **Step 1: 在 prepare-types.ts 追加 SSE 事件 payload 类型**

打开 `frontend/lib/prepare-types.ts` 文末追加：

```ts
export interface InterviewTraceNodeEvent {
  phase: "start" | "token" | "done";
  node: string;
  label?: string;
  text?: string;
  elapsedMs?: number;
  chain?: string[];
  summaryScore?: number;
}
```

- [ ] **Step 2: 改 StreamInterviewChatOptions 增加 onTraceNode**

定位 `frontend/lib/interview-chat.ts` 中 `StreamInterviewChatOptions` 类型，**追加字段**：

```ts
import type { InterviewTraceNodeEvent } from "./prepare-types";

type StreamInterviewChatOptions = {
  token: string;
  message: string;
  preparedQuestions?: import("./prepare-types").PreparedQuestion[];
  jdContext?: import("./prepare-types").JDContext | null;
  signal?: AbortSignal;
  onDelta: (text: string) => void;
  onState?: (state: InterviewProgressState) => void;
  onReport?: (report: InterviewReport) => void;
  onTraceNode?: (ev: InterviewTraceNodeEvent) => void;
};
```

- [ ] **Step 3: 改 handleSseEvent 处理新事件**

定位 `handleSseEvent` 函数，扩展为：

```ts
function handleSseEvent(
  { event, data }: SseEvent,
  onDelta: (text: string) => void,
  onState?: (state: InterviewProgressState) => void,
  onReport?: (report: InterviewReport) => void,
  onTraceNode?: (ev: import("./prepare-types").InterviewTraceNodeEvent) => void,
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

  if (event === "node_start" || event === "node_token" || event === "node_done") {
    const payload = parseJsonPayload<{
      node: string;
      label?: string;
      text?: string;
      elapsed_ms?: number;
      chain?: string[];
      summary_score?: number;
    }>(data);
    const phase = event === "node_start" ? "start" : event === "node_token" ? "token" : "done";
    onTraceNode?.({
      phase,
      node: payload.node,
      label: payload.label,
      text: payload.text,
      elapsedMs: payload.elapsed_ms,
      chain: payload.chain,
      summaryScore: payload.summary_score,
    });
    return;
  }

  if (event === "error") {
    const payload = parseJsonPayload<{ message?: string }>(data);
    throw new Error(payload.message || DEFAULT_ERROR_MESSAGE);
  }
}
```

并在 `streamInterviewChat` 函数中把 `onTraceNode` 一起传入：

定位 `await readSseStream({ stream: response.body, onEvent: (event) => handleSseEvent(event, onDelta, onState, onReport) });` 替换为：

```ts
  await readSseStream({
    stream: response.body,
    onEvent: (event) => handleSseEvent(event, onDelta, onState, onReport, onTraceNode),
  });
```

- [ ] **Step 4: 写测试**

打开 `frontend/lib/interview-chat.test.ts`（如果不存在则先看 sse.test.ts 模式新建），在文末追加：

```ts
import { describe, expect, it, vi } from "vitest";

describe("streamInterviewChat onTraceNode", () => {
  it("dispatches start/token/done with normalized payload", async () => {
    // mock fetch
    const sseBody = [
      'event: node_start',
      'data: {"node":"master","label":"MASTER"}',
      '',
      'event: node_token',
      'data: {"node":"master","text":"评估并追问"}',
      '',
      'event: node_done',
      'data: {"node":"master","elapsed_ms":120,"chain":["evaluator","followup"]}',
      '',
      'event: done',
      'data: {}',
      '',
    ].join("\n");

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sseBody));
        controller.close();
      },
    });

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } })
    );

    process.env.NEXT_PUBLIC_API_URL = "http://api.test";

    const { streamInterviewChat } = await import("./interview-chat");
    const events: any[] = [];
    await streamInterviewChat({
      token: "t",
      message: "hi",
      onDelta: () => {},
      onTraceNode: (ev) => events.push(ev),
    });

    expect(events.map((e) => e.phase)).toEqual(["start", "token", "done"]);
    expect(events[2].chain).toEqual(["evaluator", "followup"]);
    expect(events[2].elapsedMs).toBe(120);
    fetchSpy.mockRestore();
  });
});
```

- [ ] **Step 5: 跑前端测试**

```bash
cd frontend && pnpm test -- interview-chat
```

Expected: 新增用例 PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/interview-chat.ts frontend/lib/interview-chat.test.ts frontend/lib/prepare-types.ts
git commit -m "feat(frontend): add onTraceNode callback to streamInterviewChat"
```

---

# Batch E · 前端 UI

## Task 17: messages 改 discriminated union

**Files:**
- Modify: `frontend/lib/interview-chat.ts`
- Modify: `frontend/app/interview/_components/interview-chat.tsx`

- [ ] **Step 1: 在 interview-chat.ts 重新定义 InterviewChatMessage**

定位 `export type InterviewChatMessage = { role: "user" | "assistant"; content: string };`

**替换为**：

```ts
import type { TraceNodeData, PreparedQuestion } from "./prepare-types";

export type InterviewChatTextMessage = {
  role: "user" | "assistant";
  content: string;
};

export type InterviewPrepareTracePayload = {
  status: "running" | "done" | "waiting_direction";
  nodes: TraceNodeData[];
  questions: PreparedQuestion[];
  summary: string;
  direction?: string;
};

export type InterviewTurnTracePayload = {
  status: "running" | "done";
  nodes: TraceNodeData[];
  chain?: string[];
  summaryScore?: number;
  turnIndex: number;
};

export type InterviewPrepareTraceMessage = {
  role: "trace";
  kind: "prepare";
  payload: InterviewPrepareTracePayload;
};

export type InterviewTurnTraceMessage = {
  role: "trace";
  kind: "turn";
  id: string;          // 用于 onTraceNode 定位更新
  payload: InterviewTurnTracePayload;
};

export type InterviewChatMessage =
  | InterviewChatTextMessage
  | InterviewPrepareTraceMessage
  | InterviewTurnTraceMessage;

export function isTextMessage(m: InterviewChatMessage): m is InterviewChatTextMessage {
  return m.role === "user" || m.role === "assistant";
}

export function isPrepareTraceMessage(m: InterviewChatMessage): m is InterviewPrepareTraceMessage {
  return m.role === "trace" && (m as any).kind === "prepare";
}

export function isTurnTraceMessage(m: InterviewChatMessage): m is InterviewTurnTraceMessage {
  return m.role === "trace" && (m as any).kind === "turn";
}
```

- [ ] **Step 2: 跑 typecheck 看哪些地方报错**

```bash
cd frontend && pnpm typecheck
```

预计 `interview-chat.tsx` 中至少有这些位置需要修：
- `messages.map((msg) => ...)` 里直接读 `msg.content`
- `handleCopyChat` 拼接 `msg.content`
- `appendMessageText / setMessages` 多处 spread `{ role, content }`

- [ ] **Step 3: 在 interview-chat.tsx 加 type guard**

定位 `handleCopyChat` 函数，**替换内部**为：

```tsx
import { isTextMessage } from "@/lib/interview-chat";

async function handleCopyChat() {
  const lines: string[] = [];
  for (const msg of messages) {
    if (!isTextMessage(msg)) continue;
    const roleName = msg.role === "user" ? "求职者" : "面试官";
    lines.push(`【${roleName}】：${msg.content}`);
  }
  const chatText = lines.join("\n");
  // ... 其余复制逻辑不变
}
```

定位 messages 渲染（找到 `messages.map`），把每项包成：

```tsx
{messages.map((msg, index) => {
  if (msg.role === "trace" && msg.kind === "prepare") {
    return (
      <PreparationCard
        key={`prepare-${index}`}
        status={msg.payload.status}
        nodes={msg.payload.nodes}
        questions={msg.payload.questions}
        summary={msg.payload.summary}
        direction={msg.payload.direction}
        onStart={handleStartFirstQuestion}
      />
    );
  }
  if (msg.role === "trace" && msg.kind === "turn") {
    return (
      <TurnTraceCard
        key={`turn-${msg.id}`}
        status={msg.payload.status}
        nodes={msg.payload.nodes}
        turnIndex={msg.payload.turnIndex}
        summaryScore={msg.payload.summaryScore}
      />
    );
  }
  return (
    <MessageBubble
      key={`msg-${index}`}
      role={msg.role}
      content={msg.content}
    />
  );
})}
```

`TurnTraceCard` 的 import 占位（Task 18 实装）：

```tsx
import { TurnTraceCard } from "./turn-trace-card";
```

- [ ] **Step 4: 在 interview-chat.tsx 顶部的初始化 messages 处也用新结构**

定位 `setMessages` / `INITIAL_PROGRESS` 附近，把所有插入 user/assistant 消息的位置（`{ role: "user", content: text }` 等）保持原样——它们仍是合法的 `InterviewChatTextMessage`。

只需在准备阶段流入 messages：定位 `setPrepStatus("running")` 附近添加：

```tsx
// 启动准备阶段时插入一条 prepare trace 消息（作为 messages[0]）
setMessages((prev) => {
  if (prev.some((m) => m.role === "trace" && (m as any).kind === "prepare")) return prev;
  return [
    {
      role: "trace",
      kind: "prepare",
      payload: {
        status: "running",
        nodes: [],
        questions: [],
        summary: "",
        direction: undefined,
      },
    },
    ...prev,
  ];
});
```

同时把 `handlePrepareEvent` 内更新 `setTraceNodes / setPrepStatus / setPreparedQuestions / setPrepSummary / setPrepDirection` 的逻辑改为更新这条 prepare trace 消息的 payload（替代原来的独立 state）：

```tsx
function updatePrepareTraceMessage(updater: (payload: InterviewPrepareTracePayload) => InterviewPrepareTracePayload) {
  setMessages((prev) =>
    prev.map((m) =>
      m.role === "trace" && (m as any).kind === "prepare"
        ? { ...m, payload: updater((m as InterviewPrepareTraceMessage).payload) }
        : m
    )
  );
}
```

在 `handlePrepareEvent` 内把所有 `setTraceNodes(...)` 替换为对 `updatePrepareTraceMessage((p) => ({ ...p, nodes: ... }))` 的调用；`setPreparedQuestions / setPrepSummary / setPrepDirection / setPrepStatus` 同理。

完成后**删除**独立的：

```tsx
const [prepStatus, ...]
const [traceNodes, ...]
const [preparedQuestions, ...]  // 注意：preparedQuestions 仍要保留独立 state，因为 handleStartFirstQuestion 引用
const [prepSummary, ...]
const [prepDirection, ...]
```

> **保留 preparedQuestions state**：handleStartFirstQuestion 在调 streamInterviewChat 时还需要把 preparedQuestions 作为 payload 传出去，所以同时维护 messages payload 和独立 preparedQuestions state，二者在 handlePrepareEvent.done 时一起 set。

最终顶部组件状态压到：

```tsx
const [messages, setMessages] = useState<InterviewChatMessage[]>(...);
const [progress, setProgress] = useState<InterviewProgressState>(INITIAL_PROGRESS);
const [report, setReport] = useState<InterviewReport | null>(null);
const [preparedQuestions, setPreparedQuestions] = useState<PreparedQuestion[]>([]);
const [isStreaming, setIsStreaming] = useState(false);
const [showReportDelayed, setShowReportDelayed] = useState(false);
const [copied, setCopied] = useState(false);
```

- [ ] **Step 5: 不再渲染顶部固定 PreparationCard**

定位 interview-chat.tsx JSX 中 `<PreparationCard ... />`（顶部固定那张），**整体删除**该节点（它已经通过 messages 渲染了）。

- [ ] **Step 6: 跑 typecheck**

```bash
cd frontend && pnpm typecheck
```

Expected: 全绿。如果有遗漏的 m.content 访问，按 type guard 修。

- [ ] **Step 7: 跑前端测试，多个会失败（TurnTraceCard 还没实现）**

```bash
cd frontend && pnpm test -- interview-chat
```

Expected: 因 TurnTraceCard 未导入实现，可能编译失败。Task 18 实装后再跑。

- [ ] **Step 8: 暂不 commit**，等 Task 18 一起。

---

## Task 18: 新增 TurnTraceCard 组件

**Files:**
- Create: `frontend/app/interview/_components/turn-trace-card.tsx`
- Create: `frontend/app/interview/_components/turn-trace-card.test.tsx`

- [ ] **Step 1: 写测试**

```tsx
// frontend/app/interview/_components/turn-trace-card.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { TurnTraceCard } from "./turn-trace-card";

describe("TurnTraceCard", () => {
  it("renders running state with turn index", () => {
    render(
      <TurnTraceCard
        status="running"
        nodes={[
          { id: "master", label: "MASTER", status: "running", tokens: "" },
        ]}
        turnIndex={1}
      />
    );
    expect(screen.getByText(/本轮分析中/)).toBeInTheDocument();
    expect(screen.getByText(/第 1 轮/)).toBeInTheDocument();
  });

  it("renders done state with summary score", () => {
    render(
      <TurnTraceCard
        status="done"
        nodes={[
          { id: "master", label: "MASTER", status: "done", tokens: "评估并追问", elapsedMs: 120 },
          { id: "evaluator", label: "评估", status: "done", tokens: "·覆盖CAP", elapsedMs: 280 },
          { id: "followup", label: "面试官 · 追问", status: "done", tokens: "", elapsedMs: 950 },
        ]}
        turnIndex={2}
        summaryScore={7.4}
      />
    );
    expect(screen.getByText(/本轮分析完成/)).toBeInTheDocument();
    expect(screen.getByText(/7\.4/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试 FAIL**

```bash
cd frontend && pnpm test -- turn-trace-card
```

Expected: 文件不存在导致 FAIL。

- [ ] **Step 3: 实装组件**

```tsx
// frontend/app/interview/_components/turn-trace-card.tsx
"use client";

import { useEffect, useState } from "react";

import type { TraceNodeData } from "@/lib/prepare-types";
import { AgentTrace } from "./agent-trace";

interface TurnTraceCardProps {
  status: "running" | "done";
  nodes: TraceNodeData[];
  turnIndex: number;
  summaryScore?: number;
}

export function TurnTraceCard({ status, nodes, turnIndex, summaryScore }: TurnTraceCardProps) {
  const [expanded, setExpanded] = useState(status === "running");

  useEffect(() => {
    if (status === "running") {
      setExpanded(true);
    } else {
      setExpanded(false);
    }
  }, [status]);

  const isDone = status === "done";
  const headerText = isDone ? "本轮分析完成" : "本轮分析中";

  return (
    <div className="mx-0 mt-1 overflow-hidden rounded-xl border border-black/10 bg-white shadow-sm animate-in fade-in duration-300 dark:border-white/10 dark:bg-[#1c1c1a]">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between border-b border-black/10 bg-[#f7f6f2] px-4 py-3 dark:border-white/10 dark:bg-[#252523]"
      >
        <div className="flex items-center gap-2">
          <span
            className={`size-2 rounded-full flex-shrink-0 transition-all duration-300 ${
              isDone ? "bg-[#1D9E75]" : "bg-[#534AB7] animate-pulse shadow-[0_0_0_4px_rgba(83,74,183,0.12)]"
            }`}
          />
          <span className="text-xs font-bold text-[#1a1a18] dark:text-[#e8e6de]">
            {headerText} · 第 {turnIndex} 轮
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-[#8a8a8a]">
          {typeof summaryScore === "number" && (
            <span className="rounded-full bg-[#eef2ff] px-2 py-0.5 font-semibold text-[#4f46e5]">
              {summaryScore.toFixed(1)} / 10
            </span>
          )}
          <span>{expanded ? "收起" : "展开"}</span>
        </div>
      </button>
      {expanded && <AgentTrace nodes={nodes} />}
    </div>
  );
}
```

- [ ] **Step 4: 跑测试 PASS**

```bash
cd frontend && pnpm test -- turn-trace-card
```

Expected: 2 个测试 PASS。

- [ ] **Step 5: 跑 typecheck**

```bash
cd frontend && pnpm typecheck
```

Expected: 全绿。

- [ ] **Step 6: Commit**

```bash
git add frontend/app/interview/_components/turn-trace-card.tsx frontend/app/interview/_components/turn-trace-card.test.tsx frontend/app/interview/_components/interview-chat.tsx frontend/lib/interview-chat.ts
git commit -m "feat(frontend): inline TurnTraceCard rendered per turn in chat stream"
```

---

## Task 19: PreparationCard 适配 messages 流（迁移微调）

**Files:**
- Modify: `frontend/app/interview/_components/preparation-card.tsx`

- [ ] **Step 1: 检查现有 PreparationCard 接口**

```bash
grep -n "interface PreparationCardProps\|export function PreparationCard" frontend/app/interview/_components/preparation-card.tsx
```

- [ ] **Step 2: 微调样式让它与 TurnTraceCard 视觉一致**

打开 preparation-card.tsx，定位最外层 `<div ...>`，把样式与 TurnTraceCard 一致（使用 `mx-0 mt-1` 等）。**只改外层容器**，内部 trace 展示不变：

把：
```tsx
<div className="mx-0 mt-1 overflow-hidden rounded-xl border border-black/10 bg-white shadow-sm animate-in fade-in duration-300 dark:border-white/10 dark:bg-[#1c1c1a]">
```

保持不变（已经是同款样式）。

- [ ] **Step 3: 跑 typecheck + 测试**

```bash
cd frontend && pnpm typecheck && pnpm test -- preparation-card
```

Expected: 全绿。

- [ ] **Step 4: Commit**

```bash
git add frontend/app/interview/_components/preparation-card.tsx
git commit -m "style(frontend): align PreparationCard with TurnTraceCard visual"
```

---

## Task 20: InterviewChat 接线 onTraceNode + 每轮插入 turn trace

**Files:**
- Modify: `frontend/app/interview/_components/interview-chat.tsx`

- [ ] **Step 1: 在 send 函数中改造消息插入逻辑**

定位 interview-chat.tsx 中 `handleSubmit / handleSendMessage`（用户发消息的入口函数）。原本可能是：

```tsx
async function handleSendMessage(text: string) {
  setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "" }]);
  ...streamInterviewChat({...});
}
```

**替换为**：

```tsx
async function handleSendMessage(text: string) {
  if (!text.trim() || isStreaming) return;

  const turnId = crypto.randomUUID();
  const turnIndex = (progress.question_count ?? 0) + 1;

  setMessages((prev) => [
    ...prev,
    { role: "user", content: text },
    {
      role: "trace",
      kind: "turn",
      id: turnId,
      payload: {
        status: "running",
        nodes: [],
        turnIndex,
      },
    },
    { role: "assistant", content: "" },
  ]);

  const assistantIndex = messages.length + 2; // user, trace, assistant
  assistantIndexRef.current = assistantIndex;

  abortRef.current?.abort();
  const abortController = new AbortController();
  abortRef.current = abortController;
  setIsStreaming(true);

  try {
    const token = await getInterviewToken({ getToken });
    if (!token) throw new Error("登录失效");

    await streamInterviewChat({
      token,
      message: text,
      preparedQuestions,
      signal: abortController.signal,
      onState: setProgress,
      onReport: setReport,
      onDelta: (chunk) => {
        deltaBufferRef.current += chunk;
        scheduleDeltaFlush();
      },
      onTraceNode: (ev) => updateTurnTrace(turnId, ev),
    });
    flushBufferedDelta();
    finishTurnTrace(turnId);
  } catch (err) {
    if (abortController.signal.aborted) return;
    setMessages((curr) =>
      curr.map((m, i) =>
        i === assistantIndex && m.role === "assistant"
          ? { ...m, content: err instanceof Error ? err.message : "AI 暂时无法响应" }
          : m
      )
    );
  } finally {
    setIsStreaming(false);
    assistantIndexRef.current = null;
  }
}
```

- [ ] **Step 2: 实现 updateTurnTrace 和 finishTurnTrace**

在组件内追加两个函数：

```tsx
function updateTurnTrace(turnId: string, ev: import("@/lib/prepare-types").InterviewTraceNodeEvent) {
  setMessages((prev) =>
    prev.map((m) => {
      if (m.role !== "trace" || (m as any).kind !== "turn" || (m as any).id !== turnId) return m;
      const turn = m as Extract<InterviewChatMessage, { kind: "turn" }>;
      const nodes = [...turn.payload.nodes];
      const idx = nodes.findIndex((n) => n.id === ev.node);

      if (ev.phase === "start") {
        if (idx === -1) {
          nodes.push({
            id: ev.node,
            label: ev.label ?? ev.node,
            status: "running",
            tokens: "",
          });
        } else {
          nodes[idx] = { ...nodes[idx], status: "running" };
        }
      } else if (ev.phase === "token") {
        if (idx !== -1) {
          nodes[idx] = { ...nodes[idx], tokens: nodes[idx].tokens + (ev.text ?? "") };
        }
      } else if (ev.phase === "done") {
        if (idx !== -1) {
          nodes[idx] = {
            ...nodes[idx],
            status: "done",
            elapsedMs: ev.elapsedMs,
          };
        }
      }

      const summaryScore =
        ev.phase === "done" && ev.node === "evaluator"
          ? ev.summaryScore ?? turn.payload.summaryScore
          : turn.payload.summaryScore;
      const chain = ev.phase === "done" && ev.node === "master" ? ev.chain : turn.payload.chain;

      return {
        ...turn,
        payload: { ...turn.payload, nodes, summaryScore, chain },
      };
    })
  );
}

function finishTurnTrace(turnId: string) {
  setMessages((prev) =>
    prev.map((m) =>
      m.role === "trace" && (m as any).kind === "turn" && (m as any).id === turnId
        ? { ...m, payload: { ...(m as any).payload, status: "done" } }
        : m
    )
  );
}
```

- [ ] **Step 3: progress pill 不再依赖 stage**

定位 progress pill 渲染处，确保它只读 `progress.question_count` 和 `progress.total_questions`，不再用 `progress.stage` 判断（spec §11 风险点）。

- [ ] **Step 4: 更新 interview-chat.test.tsx**

确保现有用例（如 "renders opening message"）适配新结构：把所有断言里 `messages[0].content` 类型访问加 `isTextMessage()` guard。具体改动量取决于既有测试规模，逐一定位修复即可。

- [ ] **Step 5: 跑 typecheck + 全前端测试**

```bash
cd frontend && pnpm typecheck && pnpm test
```

Expected: 全绿。

- [ ] **Step 6: 跑 build**

```bash
cd frontend && pnpm build
```

Expected: build 成功。

- [ ] **Step 7: Commit**

```bash
git add frontend/app/interview/_components/interview-chat.tsx frontend/app/interview/_components/interview-chat.test.tsx
git commit -m "feat(frontend): per-turn inline TraceCard wired via onTraceNode"
```

---

# Batch F · 端到端联调

## Task 21: 后端端到端：完整一轮流程

**Files:**
- Modify: `backend/tests/integration/test_prepare_interview_integration.py`

- [ ] **Step 1: 在文件末尾追加端到端 mock 测试**

```python
@pytest.mark.asyncio
async def test_end_to_end_one_turn_emits_full_event_sequence(monkeypatch, db_session, test_user_id):
    """模拟一次完整 turn：master + evaluator + followup 节点都跑。"""
    from app.services.interview_turn import stream_interview_turn

    async def fake_graph_events(state):
        yield {"event": "node_start", "data": {"node": "master", "label": "MASTER"}}
        yield {"event": "node_token", "data": {"node": "master", "text": "评估后追问"}}
        yield {"event": "node_done", "data": {"node": "master", "elapsed_ms": 120, "chain": ["evaluator", "followup"]}}
        yield {"event": "node_start", "data": {"node": "evaluator", "label": "评估"}}
        yield {"event": "node_token", "data": {"node": "evaluator", "text": "·覆盖CAP"}}
        yield {"event": "node_done", "data": {"node": "evaluator", "elapsed_ms": 220, "summary_score": 7.0}}
        yield {"event": "node_start", "data": {"node": "followup", "label": "面试官 · 追问"}}
        yield {"event": "token", "data": {"text": "QPS"}}
        yield {"event": "token", "data": {"text": "是多少？"}}
        yield {"event": "node_done", "data": {"node": "followup", "elapsed_ms": 800}}
        yield {"event": "final", "data": {
            "stage": "interview",
            "question_count": 1, "total_questions": 5,
            "followup_count": 1, "max_followups": 2,
            "target_role": "Test",
            "assistant_message": "QPS是多少？",
            "turn_evaluations": [{
                "question_index": 1, "followup_index": 0, "bullets": ["覆盖CAP"],
                "technical_depth": 7.0, "quantified_results": 4.0,
                "failure_tradeoffs": 6.5, "structure": 7.5, "summary_score": 6.25,
            }],
        }}

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events",
        fake_graph_events,
    )

    captured = []
    async for ev in stream_interview_turn(
        message="我用 CAP 解决",
        user_id=test_user_id,
        db=db_session,
    ):
        captured.append(ev)

    node_starts = [e for e in captured if e["event"] == "node_start"]
    node_dones = [e for e in captured if e["event"] == "node_done"]
    deltas = [e for e in captured if e["event"] == "delta"]
    assert {n["data"]["node"] for n in node_starts} == {"master", "evaluator", "followup"}
    assert any(d["data"].get("text") == "QPS" for d in deltas)
    master_done = next(d for d in node_dones if d["data"]["node"] == "master")
    assert master_done["data"]["chain"] == ["evaluator", "followup"]
```

- [ ] **Step 2: 跑**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_prepare_interview_integration.py::test_end_to_end_one_turn_emits_full_event_sequence -v
```

Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_prepare_interview_integration.py
git commit -m "test(integration): end-to-end one-turn SSE event sequence"
```

---

## Task 22: 后端端到端：chain 分支覆盖

**Files:**
- Modify: `backend/tests/integration/test_prepare_interview_integration.py`

- [ ] **Step 1: 追加三种 chain 路径的端到端测试**

```python
@pytest.mark.asyncio
async def test_chain_only_followup_skips_evaluator_sse(monkeypatch, db_session, test_user_id):
    """跑题场景：master 决定 chain=['followup']，evaluator 在 SSE 里不出现。"""
    from app.services.interview_turn import stream_interview_turn

    async def fake_events(state):
        yield {"event": "node_start", "data": {"node": "master", "label": "MASTER"}}
        yield {"event": "node_done", "data": {"node": "master", "elapsed_ms": 100, "chain": ["followup"]}}
        yield {"event": "node_start", "data": {"node": "followup", "label": "面试官 · 追问"}}
        yield {"event": "token", "data": {"text": "拉回主题"}}
        yield {"event": "node_done", "data": {"node": "followup", "elapsed_ms": 400}}
        yield {"event": "final", "data": {
            "stage": "interview", "question_count": 1, "total_questions": 5,
            "followup_count": 1, "max_followups": 2,
            "assistant_message": "拉回主题",
        }}

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events",
        fake_events,
    )
    nodes = []
    async for ev in stream_interview_turn(message="...", user_id=test_user_id, db=db_session):
        if ev["event"] == "node_start":
            nodes.append(ev["data"]["node"])
    assert "evaluator" not in nodes
    assert "master" in nodes
    assert "followup" in nodes


@pytest.mark.asyncio
async def test_chain_closing_triggers_report_event(monkeypatch, db_session, test_user_id):
    """chain=['closing'] 应有 report 事件。"""
    from app.services.interview_turn import stream_interview_turn

    async def fake_events(state):
        yield {"event": "node_start", "data": {"node": "master", "label": "MASTER"}}
        yield {"event": "node_done", "data": {"node": "master", "elapsed_ms": 80, "chain": ["closing"]}}
        yield {"event": "node_start", "data": {"node": "closing", "label": "收尾"}}
        yield {"event": "token", "data": {"text": "面试结束"}}
        yield {"event": "node_done", "data": {"node": "closing", "elapsed_ms": 500}}
        yield {"event": "final", "data": {
            "stage": "closing", "question_count": 5, "total_questions": 5,
            "followup_count": 2, "max_followups": 2,
            "assistant_message": "面试结束",
            "report": {"overall_score": 7.2, "highlights": [], "improvements": []},
        }}

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events",
        fake_events,
    )
    events = []
    async for ev in stream_interview_turn(message="结束吧", user_id=test_user_id, db=db_session):
        events.append(ev["event"])
    assert "report" in events
```

- [ ] **Step 2: 跑**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_prepare_interview_integration.py -v
```

Expected: 这两个新用例 PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_prepare_interview_integration.py
git commit -m "test(integration): chain branches followup-only and closing"
```

---

## Task 23: 前端端到端：完整一轮 UI 渲染

**Files:**
- Modify: `frontend/app/interview/_components/interview-chat.test.tsx`

- [ ] **Step 1: 追加端到端 UI 测试**

在测试文件末尾追加：

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// 假设已有 ClerkProvider mock
import { InterviewChat } from "./interview-chat";

describe("InterviewChat per-turn TurnTraceCard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders turn trace card after user sends a message and progresses through nodes", async () => {
    const sseBody = [
      'event: node_start\ndata: {"node":"master","label":"MASTER"}\n',
      'event: node_token\ndata: {"node":"master","text":"评估后追问"}\n',
      'event: node_done\ndata: {"node":"master","elapsed_ms":100,"chain":["evaluator","followup"]}\n',
      'event: node_start\ndata: {"node":"evaluator","label":"评估"}\n',
      'event: node_done\ndata: {"node":"evaluator","elapsed_ms":200,"summary_score":7.4}\n',
      'event: node_start\ndata: {"node":"followup","label":"面试官 · 追问"}\n',
      'event: delta\ndata: {"text":"QPS"}\n',
      'event: delta\ndata: {"text":"是多少"}\n',
      'event: node_done\ndata: {"node":"followup","elapsed_ms":800}\n',
      'event: done\ndata: {}\n',
    ].join("\n");

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sseBody));
        controller.close();
      },
    });

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      })
    );

    render(<InterviewChat />);
    const input = await screen.findByPlaceholderText(/请输入/);
    fireEvent.change(input, { target: { value: "我答完了" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(screen.getByText(/本轮分析/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/7\.4/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/QPS是多少/)).toBeInTheDocument());
  });
});
```

> 注意：若 InterviewChat 依赖 `useAuth` / sessionStorage，则需要在 beforeEach 中 mock。参考既有 test 文件中的 mock 配方。

- [ ] **Step 2: 跑测试**

```bash
cd frontend && pnpm test -- interview-chat
```

Expected: 新用例 PASS。如果由于 mock 复杂度报错，参考既有 interview-chat.test.tsx 的 Clerk + fetch 同款 setup。

- [ ] **Step 3: 跑全量 frontend 测试 + build**

```bash
cd frontend && pnpm test && pnpm build
```

Expected: 全绿 + build 成功。

- [ ] **Step 4: Commit**

```bash
git add frontend/app/interview/_components/interview-chat.test.tsx
git commit -m "test(frontend): end-to-end TurnTraceCard rendering through full SSE turn"
```

---

## Task 24: 最终回归 & 验收

**Files:** 无新建/修改文件，跑全量验证。

- [ ] **Step 1: 后端全量**

```bash
cd backend && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy app && .venv/bin/python -m pytest tests/
```

Expected: 全绿。

- [ ] **Step 2: 前端全量**

```bash
cd frontend && pnpm typecheck && pnpm test && pnpm build
```

Expected: 全绿。

- [ ] **Step 3: 手测**：启动 dev server，从 Coach 页 → 开始面试 → 看到准备阶段 inline trace 卡 → 点开始第1题 → 答题 → 看到每轮 trace 卡（master / evaluator / followup 节点 bullet 流式打字）→ 5 题完成 → 看到 report

操作 checklist：
- [ ] Coach 页"好，今天就练这个"+"开始面试"能跳到 /interview
- [ ] /interview 顶部不再有固定卡，准备 trace 出现在 messages 流第一条
- [ ] 准备 trace 完成后默认折叠，标题"准备完成"
- [ ] 点击"开始第1题"→ 出第 1 题
- [ ] 答完第 1 题 → 聊天流插入一张 turn trace 卡 → 节点依次出现 → 卡片折叠
- [ ] turn trace 卡可展开重看
- [ ] 5 题全部完成后出 ReportCard，4 维分数与每轮平均一致
- [ ] 复制对话功能（handleCopyChat）正确跳过 trace 消息

- [ ] **Step 4: 最终 commit（如果手测中发现样式微调）**

按需提交 polishing commits。

---

## 自检清单

- [x] Spec §3 推翻清单中所有节点 / prompts / state 字段 → Task 1-5 完整覆盖
- [x] Spec §5 拓扑（4 子 agent 池 + chain 动态）→ Task 7-11
- [x] Spec §6.2 master_node 双相 + 5 条合法性约束 → Task 7、8
- [x] Spec §6.3 evaluator_node 双相 + turn_evaluations → Task 9
- [x] Spec §6.4 followup_node 自己生成追问 → Task 3 (重做 nodes.py) + Task 2 (FOLLOWUP_SYSTEM_PROMPT)
- [x] Spec §6.5 report_node 聚合 → Task 10
- [x] Spec §6.6 移除节点清单 → Task 1、2、3、4、5
- [x] Spec §6.7 SSE 改造 → Task 12-14
- [x] Spec §7.1 PreparationCard 迁移到 messages 流 → Task 17
- [x] Spec §7.2 TurnTraceCard 新组件 → Task 18
- [x] Spec §7.3 streamInterviewChat onTraceNode → Task 16
- [x] Spec §7.4 InterviewChat 每轮 trace + onTraceNode 接线 → Task 20
- [x] Spec §7.5 抽 prepare-types → Task 15
- [x] Spec §8.2 完整 SSE 事件序列 → Task 12 + 14 + 21、22
- [x] Spec §9 错误处理（master Phase 1/2 失败、evaluator 失败、report 降级）→ Task 8、9、10
- [x] Spec §10 全部测试用例 → Task 7、9、10、11、14、21、22、23
- [x] Spec §11 风险（progress pill 不依赖 stage、handleCopyChat 过滤 trace）→ Task 17、20
