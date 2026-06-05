"""Chief Interviewer ReAct-loop nodes."""
from __future__ import annotations

import asyncio
import json
from typing import Any, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agents.designer import run_designer, run_designer_dual
from app.agents.evaluator import run_evaluator
from app.agents.interviewer.chief_prompts import CHIEF_SYSTEM_PROMPT
from app.agents.interviewer.nodes import (
    _chat_model,
    _generate_text,
    closing_node,
    generate_prepared_question_reply,
)
from app.agents.interviewer.prompts import CLOSING_SYSTEM_PROMPT
from app.agents.interviewer.state import InterviewState, TurnEvaluation
from app.core.logging import get_logger

log = get_logger("app.agents.interviewer.chief")

MAX_CHIEF_ITERATIONS = 4

TERMINATION_KEYWORDS = (
    "结束",
    "结束吧",
    "结束面试",
    "到此为止",
    "不面了",
    "不想继续",
    "我说完了",
    "我答完了",
    "够了",
    "算了",
    "停止",
    "退出",
    "再见",
    "拜拜",
)

SKIP_KEYWORDS = (
    "跳过",
    "跳过这题",
    "跳过这个问题",
    "下一题",
    "下一个问题",
    "换一题",
    "换个问题",
    "不会答",
    "不想答",
    "先不答",
)


class _DesignQuestionArgs(BaseModel):
    focus: str = Field(
        default="new_question",
        description='"new_question" 表示只准备新题；"dual" 表示同时准备追问和新题。',
    )


def _last_human_message(state: InterviewState) -> str:
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
            return str(getattr(m, "content", ""))
    return ""


def _conversation_context(state: InterviewState) -> str:
    lines: list[str] = []
    for m in state.get("messages", [])[-8:]:
        role = "面试官" if isinstance(m, AIMessage) or getattr(m, "type", "") == "ai" else "候选人"
        lines.append(f"{role}：{str(getattr(m, 'content', ''))[:500]}")
    return "\n".join(lines)


def _previous_questions(state: InterviewState) -> list[str]:
    questions: list[str] = []
    for m in state.get("messages", [])[-20:]:
        if isinstance(m, AIMessage) or getattr(m, "type", "") == "ai":
            text = str(getattr(m, "content", "")).strip()
            if text:
                questions.append(text)
    prepared = state.get("prepared_questions") or []
    for item in prepared[: state.get("current_question_index", 0)]:
        if item.get("question"):
            questions.append(str(item["question"]))
    return questions


def _wants_to_end(text: str) -> bool:
    compact = text.strip()
    return bool(compact) and len(compact) < 20 and any(kw in compact for kw in TERMINATION_KEYWORDS)


def _wants_to_skip(text: str) -> bool:
    compact = text.strip()
    return bool(compact) and len(compact) < 30 and any(kw in compact for kw in SKIP_KEYWORDS)


def _score(report: dict[str, Any] | None) -> float:
    scoring = (report or {}).get("scoring") or {}
    try:
        return float(scoring.get("summary_score", 0))
    except (TypeError, ValueError):
        return 0.0


def _missing_dimensions(report: dict[str, Any] | None) -> list[str]:
    scoring = (report or {}).get("scoring") or {}
    return [str(m) for m in scoring.get("missing_dimensions") or [] if str(m).strip()]


def _answer_is_sufficient(report: dict[str, Any] | None) -> bool:
    scoring = (report or {}).get("scoring") or {}
    if scoring.get("is_repeated_answer"):
        return True
    if not scoring.get("followup_would_help", True):
        return True
    return _score(report) >= 7.0 and not _missing_dimensions(report)


def _should_close_after_evaluation(state: InterviewState) -> bool:
    if not state.get("evaluator_report"):
        return False
    if state.get("question_count", 0) < state.get("total_questions", 5):
        return False
    return _answer_is_sufficient(state.get("evaluator_report")) or (
        state.get("followup_count", 0) >= state.get("max_followups", 2)
    )


def _followup_focus(report: dict[str, Any] | None) -> str:
    missing = _missing_dimensions(report)
    if missing:
        return " / ".join(missing[:3])
    report_text = str((report or {}).get("report_text") or "").strip()
    if report_text:
        return report_text[:120]
    return "回答深度不足，请围绕上一题补充具体例子、权衡或量化结果"


def _message_content_text(message: BaseMessage) -> str:
    content = message.content
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


def _fallback_tool_calls(state: InterviewState) -> list[dict[str, Any]]:
    latest_answer = _last_human_message(state)
    if _wants_to_end(latest_answer):
        return []
    if state.get("designer_output"):
        return []
    if state.get("question_count", 0) == 0:
        return [{"name": "design_question", "args": {"focus": "new_question"}, "id": "fallback_design"}]
    if (
        latest_answer
        and not state.get("evaluator_report")
        and not state.get("designer_dual_output")
        and state.get("question_count", 0) >= state.get("total_questions", 5)
    ):
        return [{"name": "evaluate_answer", "args": {}, "id": "fallback_eval"}]
    if latest_answer and not state.get("evaluator_report") and not state.get("designer_dual_output"):
        return [
            {"name": "evaluate_answer", "args": {}, "id": "fallback_eval"},
            {"name": "design_question", "args": {"focus": "dual"}, "id": "fallback_design"},
        ]
    if _should_close_after_evaluation(state):
        return []
    if state.get("evaluator_report") and not state.get("designer_dual_output"):
        return [{"name": "design_question", "args": {"focus": "dual"}, "id": "fallback_design"}]
    return []


def _chief_context(state: InterviewState) -> str:
    parts = [
        f"题目进度：{state.get('question_count', 0)} / {state.get('total_questions', 5)}",
        f"追问次数：{state.get('followup_count', 0)} / {state.get('max_followups', 2)}",
    ]
    if state.get("target_role"):
        parts.append(f"目标岗位：{state['target_role']}")

    job_intel = state.get("job_intel") or {}
    cp = job_intel.get("company_profile") or {}
    if cp.get("summary"):
        tags = cp.get("tags") or []
        tags_str = f"（关键词：{', '.join(tags)}）" if tags else ""
        parts.append(
            f"面试官 persona 提示：你正在以 {state.get('target_company') or '本公司'} 的风格主持面试。"
            f"公司画像：{cp['summary']}{tags_str}"
        )

    evaluator_report = state.get("evaluator_report") or {}
    if evaluator_report:
        raw_report = str(evaluator_report.get("report_text", ""))[:200]
        parts.append(f"[eval_summary] {raw_report}")
    designer_output = state.get("designer_output") or {}
    if designer_output:
        parts.append(f"出题专家输出：{designer_output.get('question_text', '')}")
    designer_dual_output = state.get("designer_dual_output") or {}
    if designer_dual_output:
        parts.append(
            "出题专家双方案："
            f"追问={designer_dual_output.get('followup_question', '')[:120]}；"
            f"新题={designer_dual_output.get('new_question', '')[:120]}"
        )
    latest = _last_human_message(state)
    if latest:
        parts.append(f"候选人最新回答：{latest[:500]}")
    return "\n".join(parts)


def _pick_from_dual_output(state: InterviewState) -> dict[str, Any]:
    """从 designer_dual_output 中规则选题，不调 LLM。返回 next_state 补丁。"""
    eval_report = state.get("evaluator_report")
    dual = state.get("designer_dual_output") or {}
    answer_sufficient = _answer_is_sufficient(eval_report)
    if state.get("question_count", 0) >= state.get("total_questions", 5) and (
        answer_sufficient or state.get("followup_count", 0) >= state.get("max_followups", 2)
    ):
        return {"designer_dual_output": None}

    picked = _pick_question(
        eval_report,
        dual,
        state.get("followup_count", 0),
        state.get("max_followups", 2),
    )
    is_followup = not answer_sufficient and state.get("followup_count", 0) < state.get("max_followups", 2)
    picked_source = (
        dual.get("followup_source", "llm")
        if is_followup
        else dual.get("new_question_source", dual.get("source", "llm"))
    )
    return {
        "designer_output": {
            "question_text": picked,
            "question_category": dual.get("question_category", "technical"),
            "focus_area": dual.get("focus_area", "dual"),
            "source": picked_source,
        },
        "designer_dual_output": None,
    }


async def chief_think(state: InterviewState) -> InterviewState:
    iteration = state.get("chief_iteration", 0)
    thoughts = list(state.get("chief_thoughts") or [])
    if iteration >= MAX_CHIEF_ITERATIONS:
        thoughts.append("Chief loop 达到上限，降级为直接回复。")
        return cast(InterviewState, {**dict(state), "chief_thoughts": thoughts})

    latest_answer = _last_human_message(state)
    if _wants_to_skip(latest_answer) and state.get("question_count", 0) > 0:
        thoughts.append("候选人要求跳过当前问题，直接进入下一题。")
        designed = await _execute_design(state, focus="new_question")
        return cast(InterviewState, {
            **dict(state),
            "designer_output": designed,
            "designer_dual_output": None,
            "evaluator_report": None,
            "chief_thoughts": thoughts,
        })

    # 已有 eval+design 结果时直接选题，跳过本轮 LLM 调用
    if iteration > 0 and state.get("evaluator_report") and state.get("designer_dual_output"):
        chief_messages = list(state.get("chief_messages") or [])
        chief_messages.append(AIMessage(content="已收集评估和出题结果，直接进入回复。"))
        return cast(InterviewState, {
            **dict(state),
            **_pick_from_dual_output(state),
            "chief_messages": chief_messages,
            "chief_thoughts": thoughts,
        })

    chief_messages = list(state.get("chief_messages") or [])
    if not chief_messages:
        prompt = CHIEF_SYSTEM_PROMPT.format(context=_chief_context(state))
        human_text = latest_answer or "请启动本轮面试。"
        chief_messages = [SystemMessage(content=prompt), HumanMessage(content=human_text)]

    partial: dict[str, Any] = {}
    tools = _make_chief_tools(state, partial)
    try:
        model = _chat_model(fast=True, streaming=True).bind_tools(tools).with_config(tags=["chief_think_token_stream"])
        chunks = []
        response: Any
        async for chunk in model.astream(chief_messages):
            chunks.append(chunk)
        if chunks:
            response = chunks[0]
            for chunk in chunks[1:]:
                response += chunk
        else:
            response = AIMessage(content="")
        
        if not isinstance(response, AIMessage):
            response = AIMessage(content=_message_content_text(cast(BaseMessage, response)))
    except Exception as exc:
        log.warning("chief_tool_calling_failed", error=str(exc))
        response = AIMessage(content="Chief LLM 调用失败，降级为直接回复。")

    if not response.tool_calls:
        fallback_calls = _fallback_tool_calls(state)
        if fallback_calls:
            log.warning(
                "chief_missing_tool_calls_fallback",
                question_count=state.get("question_count", 0),
                tools=[str(call.get("name", "")) for call in fallback_calls],
            )
            response = AIMessage(
                content=_message_content_text(response),
                tool_calls=fallback_calls,
            )

    chief_messages.append(response)
    content = _message_content_text(response).strip()
    if content:
        thoughts.append(content)

    next_state: dict[str, Any] = {
        **dict(state),
        **partial,
        "chief_messages": chief_messages,
        "chief_thoughts": thoughts,
    }
    if not response.tool_calls and state.get("evaluator_report") and state.get("designer_dual_output"):
        next_state.update(_pick_from_dual_output(state))
    return cast(InterviewState, next_state)


async def _execute_evaluate(state: InterviewState) -> dict[str, Any]:
    report = await run_evaluator(
        {
            "session_id": state.get("session_id", ""),
            "user_id": state.get("user_id", ""),
            "target_role": state.get("target_role", ""),
            "latest_answer": _last_human_message(state),
            "conversation_context": _conversation_context(state),
            "existing_profile": state.get("candidate_profile") or {},
            "question_index": state.get("current_question_index", state.get("question_count", 0)),
            "followup_index": state.get("followup_count", 0),
            "db": state.get("db"),
            "job_intel": state.get("job_intel"),
        }
    )
    return report


async def _execute_design(state: InterviewState, focus: str = "new_question") -> dict[str, Any]:
    return await run_designer(
        {
            "focus": focus,
            "target_role": state.get("target_role", ""),
            "target_company": state.get("target_company", ""),
            "user_background": state.get("user_background", ""),
            "candidate_profile": state.get("candidate_profile") or {},
            "jd_context": state.get("jd_context"),
            "job_intel": state.get("job_intel"),
            "previous_questions": _previous_questions(state),
            "prepared_questions": state.get("prepared_questions") or [],
            "current_question_index": state.get("current_question_index", state.get("question_count", 0)),
            "evaluator_report": state.get("evaluator_report"),
            "messages": state.get("messages", []),
        }
    )


def _pick_question(
    eval_report: dict[str, Any] | None,
    designer_dual: dict[str, Any],
    followup_count: int,
    max_followups: int,
) -> str:
    answer_sufficient = _answer_is_sufficient(eval_report)
    if answer_sufficient or followup_count >= max_followups:
        return str(designer_dual.get("new_question") or "")
    return str(designer_dual.get("followup_question") or "")


async def _execute_design_dual(state: InterviewState) -> dict[str, Any]:
    return await run_designer_dual(
        {
            "focus": "dual",
            "target_role": state.get("target_role", ""),
            "target_company": state.get("target_company", ""),
            "user_background": state.get("user_background", ""),
            "candidate_profile": state.get("candidate_profile") or {},
            "jd_context": state.get("jd_context"),
            "job_intel": state.get("job_intel"),
            "previous_questions": _previous_questions(state),
            "prepared_questions": state.get("prepared_questions") or [],
            "current_question_index": state.get("current_question_index", state.get("question_count", 0)),
            "evaluator_report": None,
            "messages": state.get("messages", []),
        }
    )


def _make_chief_tools(state: InterviewState, partial: dict[str, Any]) -> list[StructuredTool]:
    async def _evaluate_answer() -> str:
        """评估候选人最新回答的质量，更新画像，返回决策建议。"""
        try:
            report = await _execute_evaluate(state)
        except Exception as exc:
            log.error("chief_evaluate_answer_failed", error=str(exc))
            report = {"error": str(exc), "scoring": {}}
        scoring = report.get("scoring") or {}
        updated_evals = list(state.get("turn_evaluations") or [])
        if scoring:
            updated_evals.append(cast(TurnEvaluation, scoring))

        partial["evaluator_report"] = report
        partial["candidate_profile"] = report.get("updated_profile") or state.get("candidate_profile") or {}
        partial["turn_evaluations"] = updated_evals
        return json.dumps(
            {
                "summary_score": scoring.get("summary_score"),
                "report_text": report.get("report_text"),
                "missing_dimensions": scoring.get("missing_dimensions", []),
            },
            ensure_ascii=False,
        )

    async def _design_question(focus: str = "new_question") -> str:
        """设计下一个面试问题或追问。focus 可取 new_question 或 dual。"""
        try:
            if focus == "dual":
                result = await _execute_design_dual(cast(InterviewState, {**dict(state), **partial}))
                partial["designer_dual_output"] = result
            else:
                result = await _execute_design(cast(InterviewState, {**dict(state), **partial}), focus=focus)
                partial["designer_output"] = result
        except Exception as exc:
            log.warning("chief_design_question_failed", focus=focus, error=str(exc))
            result = {"error": str(exc)}
        return json.dumps(result, ensure_ascii=False)

    async def _query_profile() -> str:
        """获取候选人当前能力画像摘要，不触发 LLM。"""
        profile = {
            **dict(state.get("candidate_profile") or {}),
            **dict(partial.get("candidate_profile") or {}),
        }
        return json.dumps(profile, ensure_ascii=False)

    return [
        StructuredTool.from_function(
            coroutine=_evaluate_answer,
            name="evaluate_answer",
            description="评估候选人最新回答的质量，更新候选人画像，并返回评分、缺失维度和建议。",
        ),
        StructuredTool.from_function(
            coroutine=_design_question,
            name="design_question",
            description='设计下一道问题。focus="new_question" 只生成新题；focus="dual" 同时生成追问和新题。',
            args_schema=_DesignQuestionArgs,
        ),
        StructuredTool.from_function(
            coroutine=_query_profile,
            name="query_profile",
            description="读取当前候选人能力画像摘要，不调用外部 LLM。",
        ),
    ]


async def chief_execute(state: InterviewState) -> InterviewState:
    results = list(state.get("chief_tool_results") or [])
    partial: dict[str, Any] = {}
    chief_messages = list(state.get("chief_messages") or [])
    last = chief_messages[-1] if chief_messages else None
    tool_calls = getattr(last, "tool_calls", None) or []
    tools = {tool.name: tool for tool in _make_chief_tools(state, partial)}

    async def _run_tool_call(tool_call: dict[str, Any]) -> tuple[dict[str, Any], str]:
        name = str(tool_call.get("name") or "")
        args = tool_call.get("args") or {}
        tool = tools.get(name)
        if tool is None:
            return tool_call, json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
        try:
            content = await tool.ainvoke(args)
            return tool_call, str(content)
        except Exception as exc:
            log.error("chief_tool_execute_failed", tool=name, error=str(exc))
            return tool_call, json.dumps({"error": str(exc)}, ensure_ascii=False)

    executed = await asyncio.gather(*[_run_tool_call(tc) for tc in tool_calls])
    for tool_call, content in executed:
        name = str(tool_call.get("name") or "")
        call_id = str(tool_call.get("id") or name)
        chief_messages.append(ToolMessage(content=content, tool_call_id=call_id, name=name))
        result_record: dict[str, Any] = {"tool": name, "result": content}
        if "error" in content:
            result_record["error"] = content
        results.append(result_record)

    return cast(InterviewState, {
        **dict(state),
        **partial,
        "chief_iteration": state.get("chief_iteration", 0) + 1,
        "chief_messages": chief_messages,
        "chief_tool_results": results,
    })


async def _question_reply(state: InterviewState, designed: dict[str, Any]) -> str:
    question_text = str(designed.get("question_text") or "").strip()
    if designed.get("source") == "prepared":
        next_count = state.get("question_count", 0) + 1
        return await generate_prepared_question_reply(
            question_text,
            cast(InterviewState, {**dict(state), "question_count": next_count}),
        )
    return question_text


async def chief_respond(state: InterviewState) -> InterviewState:
    latest_answer = _last_human_message(state)
    if _wants_to_end(latest_answer):
        return await closing_node(state)

    designed = state.get("designer_output") or {}
    if designed.get("question_text"):
        is_new_question = designed.get("source") == "prepared" or (
            state.get("evaluator_report") is not None
            and _answer_is_sufficient(state.get("evaluator_report"))
        ) or state.get("followup_count", 0) >= state.get("max_followups", 2)
        if state.get("question_count", 0) == 0:
            is_new_question = True

        if is_new_question:
            next_count = state.get("question_count", 0) + 1
            idx = state.get("current_question_index", state.get("question_count", 0))
            idx_delta = 1 if designed.get("source") == "prepared" else 0
            return {
                "stage": "interview",
                "question_count": next_count,
                "followup_count": 0,
                "current_question_index": idx + idx_delta,
                "assistant_message": await _question_reply(state, designed),
                "evaluator_report": None,
                "designer_output": None,
                "designer_dual_output": None,
            }
        return {
            "stage": "interview",
            "followup_count": state.get("followup_count", 0) + 1,
            "assistant_message": str(designed["question_text"]),
            "evaluator_report": None,
            "designer_output": None,
            "designer_dual_output": None,
        }

    try:
        text = await _generate_text(CLOSING_SYSTEM_PROMPT, state)
    except Exception as exc:
        log.warning("chief_respond_fallback_failed", error=str(exc))
        text = "本轮模拟面试先到这里。系统会根据刚才的对话生成结构化评估报告。"
    return {"stage": "closing", "assistant_message": text}


def route_after_chief_think(state: InterviewState) -> str:
    msgs = state.get("chief_messages") or []
    last = msgs[-1] if msgs else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return "chief_execute"
    return "chief_respond"


def route_after_chief_respond(state: InterviewState) -> str:
    return "report" if state.get("stage") == "closing" else "__end__"
