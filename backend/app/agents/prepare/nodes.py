# backend/app/agents/prepare/nodes.py
"""Node functions for the prepare pipeline."""
from __future__ import annotations

import json as _json
from typing import Any, Literal, cast

from langchain_core.messages import SystemMessage
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agents.prepare.prompts import SUPERVISOR_COMBINED_PROMPT
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
        completed = state.get("completed_tools", [])
        return {**state, "weak_areas": [], "completed_tools": completed + ["memory_search"]}

    sessions = await _get_recent_sessions(user_id)

    weak_areas = _extract_weak_areas(sessions)

    log.info(
        "memory_search_done",
        user_id=user_id,
        weak_count=len(weak_areas),
    )
    completed = state.get("completed_tools", [])
    return {**state, "weak_areas": weak_areas, "completed_tools": completed + ["memory_search"]}


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
        completed = state.get("completed_tools", [])
        return {**state, "jd_context": None, "completed_tools": completed + ["jd_analysis"]}

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
    completed = state.get("completed_tools", [])
    return {**state, "jd_context": jd_context, "completed_tools": completed + ["jd_analysis"]}


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
    completed = state.get("completed_tools", [])
    return {
        **state,
        "prepared_questions": questions,
        "summary": summary,
        "completed_tools": completed + ["question_gen"],
    }


# ─────────────────────────────────────────────
# SUPERVISOR
# ─────────────────────────────────────────────

class SupervisorDecision(BaseModel):
    next: Literal["memory_search", "jd_analysis", "question_gen", "need_direction", "END"]
    direction: str = ""
    reasoning: str = ""

def _build_state_summary(state: PrepareState) -> str:
    """将当前 state 转为可读快照供 Supervisor 参考。"""
    user_direction = state.get("user_direction") or ""
    jd_raw = state.get("jd_raw") or ""
    weak_areas = state.get("weak_areas") or []
    jd_context = state.get("jd_context")
    completed = state.get("completed_tools", [])

    summary = [
        f"用户目标方向: {user_direction or '未提供'}",
        f"是否提供 JD: {'是' if jd_raw else '否'}",
        f"历史薄弱点: {', '.join(weak_areas) if weak_areas else '无'}",
        f"JD 分析结果: {'已完成' if jd_context else '未完成'}",
        f"已运行 Agent: {', '.join(completed) if completed else '无'}",
    ]
    return "\n".join(summary)

async def supervisor_node(state: PrepareState) -> PrepareState:
    """Supervisor Loop 中央调度节点。"""
    # 1. 防死循环检查
    iteration = state.get("iteration_count", 0)
    if iteration >= 6:
        log.warning("supervisor_max_iterations_reached", iteration=iteration)
        return {**state, "next_action": "END", "iteration_count": iteration + 1}

    state_summary = _build_state_summary(state)
    completed_tools = state.get("completed_tools", [])

    log.info("supervisor_node_start", iteration=iteration, completed=completed_tools)

    # 单次流式调用：推理可见 token + 末行 JSON 决策，避免原两次串行 gpt-4o 调用的双倍延迟
    combined_prompt = SUPERVISOR_COMBINED_PROMPT.format(
        state_summary=state_summary,
        completed_tools=", ".join(completed_tools) if completed_tools else "无",
    )
    model_stream = _llm(streaming=True).with_config(tags=["prepare_supervisor_stream"])

    @_retry_llm
    async def _stream_combined() -> str:
        result = ""
        async for chunk in model_stream.astream([SystemMessage(content=combined_prompt)]):
            content = chunk.content if isinstance(chunk.content, str) else ""
            result += content
        return result

    full_text = await _stream_combined()

    # 逐行找 DECISION: {…} 行，避免贪婪 regex 误匹配推理文本中的花括号
    decision = SupervisorDecision(next="END")
    for line in full_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("DECISION:"):
            json_str = stripped[len("DECISION:"):].strip()
            try:
                raw = _json.loads(json_str)
                decision = SupervisorDecision(
                    next=raw.get("next", "END"),
                    direction=raw.get("direction", ""),
                    reasoning=raw.get("reasoning", ""),
                )
            except (_json.JSONDecodeError, ValueError, TypeError) as exc:
                log.warning("supervisor_decision_parse_failed", error=str(exc), raw=json_str)
            break
    else:
        log.warning("supervisor_decision_not_found", raw=full_text[-300:])
        try:
            model_structured = _llm().with_structured_output(SupervisorDecision)
            decision = await model_structured.ainvoke([SystemMessage(content=combined_prompt)])
        except Exception as exc:
            log.warning("supervisor_structured_fallback_failed", error=str(exc))
            decision = SupervisorDecision(next="END")

    # 强制防重复：如果 LLM 建议跑已跑过的工具，强制 END（除非是特殊状态）
    if decision.next in completed_tools:
        log.warning("supervisor_loop_detected", tool=decision.next)
        decision.next = "END"

    updates: dict[str, Any] = {
        "next_action": decision.next,
        "iteration_count": iteration + 1,
        "need_direction": decision.next == "need_direction",
    }
    if decision.direction:
        updates["direction"] = decision.direction

    log.info(
        "supervisor_done",
        next=decision.next,
        direction=decision.direction,
        reasoning=decision.reasoning
    )
    return cast(PrepareState, {**dict(state), **updates})
