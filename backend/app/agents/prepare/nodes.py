# backend/app/agents/prepare/nodes.py
"""Node functions for the prepare pipeline."""
from __future__ import annotations

from typing import Any

from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agents.prepare.state import PrepareState
from app.core.logging import get_logger

log = get_logger("app.agents.prepare.nodes")

_RETRYABLE = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)

_retry_llm = retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    reraise=True,
)


# ─────────────────────────────────────────────
# 内部 DB 查询助手
# ─────────────────────────────────────────────

async def _get_recent_sessions(user_id: str, limit: int = 5) -> list[Any]:
    """读取用户最近 N 场面试 session（含 report_json 字段）。"""
    from sqlalchemy import desc, select

    from app.db.session import async_session_factory
    from app.models.core import InterviewSession

    async with async_session_factory() as db:
        result = await db.execute(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(desc(InterviewSession.started_at))
            .limit(limit)
        )
        return list(result.scalars().all())


def _extract_weak_areas(sessions: list[Any]) -> list[str]:
    """从历史 session report 提取薄弱点描述。"""
    weak = []
    for s in sessions:
        # 避免 MagicMock 默认生成属性的坑，只接受真正的 dict 属性
        report_json = getattr(s, "report_json", None)
        if isinstance(report_json, dict):
            report = report_json
        else:
            report_val = getattr(s, "report", None)
            report = report_val if isinstance(report_val, dict) else {}

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
    """查询历史面试表现，填充 weak_areas。"""
    user_id = state.get("user_id", "")
    if not user_id:
        return {**state, "weak_areas": []}

    sessions = await _get_recent_sessions(user_id)

    weak_areas = _extract_weak_areas(sessions)

    log.info(
        "memory_search_done",
        user_id=user_id,
        weak_count=len(weak_areas),
    )
    return {**state, "weak_areas": weak_areas}


def _llm(streaming: bool = False, timeout: int = 30) -> Any:
    from langchain_openai import ChatOpenAI

    from app.core.config import get_settings

    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model_chat,
        api_key=settings.openai_api_key,
        timeout=timeout,
        streaming=streaming,
    )



class _JDContextModel(BaseModel):
    company: str = ""
    role: str = ""
    key_skills: list[str] = []
    focus_areas: list[str] = []
    difficulty: str = "medium"


async def jd_analysis_node(state: PrepareState) -> PrepareState:
    """JD 文本 → 结构化 JDContext。无 JD 时直接跳过。"""
    from langchain_core.messages import SystemMessage

    from app.agents.prepare.prompts import JD_ANALYSIS_SYSTEM_PROMPT
    from app.agents.prepare.state import JDContext

    jd_raw = state.get("jd_raw")
    if not jd_raw:
        return {**state, "jd_context": None}

    prompt = JD_ANALYSIS_SYSTEM_PROMPT.format(jd_raw=jd_raw[:4000])
    model = _llm().with_structured_output(_JDContextModel)

    @_retry_llm
    async def _invoke() -> _JDContextModel:
        return await model.ainvoke([SystemMessage(content=prompt)])  # type: ignore[return-value]

    output: _JDContextModel = await _invoke()

    jd_context: JDContext = {
        "company": output.company,
        "role": output.role,
        "key_skills": output.key_skills,
        "focus_areas": output.focus_areas,
        "difficulty": output.difficulty,
    }
    log.info("jd_analysis_done", role=output.role, skills_count=len(output.key_skills))
    return {**state, "jd_context": jd_context}


async def question_gen_node(state: PrepareState) -> PrepareState:
    """基于方向 + 薄弱点生成 5 道定制题目（流式输出）。"""
    import json
    import re

    from langchain_core.messages import SystemMessage

    from app.agents.prepare.prompts import QUESTION_GEN_SYSTEM_PROMPT
    from app.agents.prepare.state import PreparedQuestion

    direction = state.get("direction") or state.get("user_direction") or "通用软件工程师"
    target_role = state.get("user_direction") or direction
    weak_areas = state.get("weak_areas") or []
    jd_context = state.get("jd_context")

    jd_block = ""
    if jd_context:
        jd_block = f"JD 考点：{', '.join(jd_context.get('focus_areas', []))}\n技术栈：{', '.join(jd_context.get('key_skills', []))}"

    weak_block = f"历史薄弱点（优先出题）：{', '.join(weak_areas)}" if weak_areas else ""

    prompt = QUESTION_GEN_SYSTEM_PROMPT.format(
        count=5,
        direction=direction,
        target_role=target_role,
        jd_context_block=jd_block,
        weak_areas_block=weak_block,
    )

    # 流式调用，tagged 供 SSE 捕获
    model = _llm(streaming=True).with_config(tags=["prepare_question_gen_stream"])
    full_text = ""
    async for chunk in model.astream([SystemMessage(content=prompt)]):
        content = chunk.content if isinstance(chunk.content, str) else ""
        full_text += content

    def _safe_int(val: Any, default: int) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    # 解析 JSON 数组
    questions: list[PreparedQuestion] = []
    try:
        json_match = re.search(r"\[.*\]", full_text, re.DOTALL)
        if json_match:
            raw_list = json.loads(json_match.group())
            questions = sorted(
                [
                    {
                        "id": _safe_int(q.get("id"), i + 1),
                        "question": str(q["question"]),
                        "category": q.get("category", "technical"),
                        "focus_area": str(q.get("focus_area", "")),
                        "priority": _safe_int(q.get("priority"), 5),
                    }
                    for i, q in enumerate(raw_list)
                ],
                key=lambda x: x["priority"],
            )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        log.error("question_gen_parse_failed", error=str(exc), raw=full_text[:500])

    # 生成一句话摘要
    summary = ""
    if questions:
        summary = f"已根据你的背景和目标岗位为你定制了 {len(questions)} 道面试题，点击下方按钮开始练习。"
    else:
        summary = "题目生成遇到了一点小问题，你可以点击下方按钮直接开始面试，我将为你实时出题。"

    log.info("question_gen_done", count=len(questions))
    return {**state, "prepared_questions": questions, "summary": summary}


class _MasterDecision(BaseModel):
    direction: str = ""
    chain: list[str] = []
    need_direction: bool = False


VALID_PREPARE_NODES = {"memory_search", "jd_analysis", "question_gen"}


async def master_node(state: PrepareState) -> PrepareState:
    """识别练习方向，决定调用链。流式输出推理 bullets，结构化输出决策。"""
    from langchain_core.messages import SystemMessage

    from app.agents.prepare.prompts import (
        MASTER_DECISION_PROMPT,
        MASTER_REASONING_PROMPT,
    )

    user_direction = state.get("user_direction") or ""
    jd_raw = state.get("jd_raw") or ""
    weak_areas = state.get("weak_areas") or []

    log.info("master_node_start", user_direction=user_direction, jd_raw_len=len(jd_raw))

    context = f"""
用户档案：
  - 目标岗位/方向：{user_direction or "未设置"}
  - 是否提供 JD：{"是" if jd_raw else "否"}
  - 历史薄弱点：{", ".join(weak_areas) if weak_areas else "无（新用户或未查询）"}
""".strip()

    # Phase 1: 流式推理（供 SSE 捕获，用户可见）
    reasoning_prompt = MASTER_REASONING_PROMPT.format(context=context)
    model_stream = _llm(streaming=True).with_config(tags=["prepare_master_stream"])
    async for _ in model_stream.astream([SystemMessage(content=reasoning_prompt)]):
        pass  # 流由 astream_events 在 graph 层捕获，此处只触发

    # Phase 2: 结构化决策（快速，非流式）
    decision_prompt = MASTER_DECISION_PROMPT.format(context=context)
    model_decision = _llm().with_structured_output(_MasterDecision)

    @_retry_llm
    async def _invoke_decision() -> _MasterDecision:
        return await model_decision.ainvoke([SystemMessage(content=decision_prompt)])  # type: ignore[return-value]

    decision: _MasterDecision = await _invoke_decision()

    # [C3] 保证 question_gen 始终在 chain 末尾，并过滤非法节点
    chain = [n for n in decision.chain if n in VALID_PREPARE_NODES]
    chain = list(dict.fromkeys(chain + ["question_gen"]))

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



