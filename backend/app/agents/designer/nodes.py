"""Node functions for the Question Designer Agent."""
from __future__ import annotations

from typing import Any, cast

from langchain_core.messages import BaseMessage, SystemMessage
from pydantic import BaseModel

from app.agents.designer.prompts import DESIGNER_DUAL_SYSTEM_PROMPT, DESIGNER_SYSTEM_PROMPT
from app.agents.designer.state import DesignerState
from app.agents.interviewer.nodes import _chat_model
from app.core.logging import get_logger

log = get_logger("app.agents.designer.nodes")


class _DesignedQuestion(BaseModel):
    question_text: str = ""
    question_category: str = "technical"
    focus_area: str = ""


class _DesignerDualOutput(BaseModel):
    followup_question: str = ""
    new_question: str = ""


GENERIC_PATTERNS = (
    "展开说说",
    "详细说说",
    "为什么这么做",
    "有没有代码",
    "代码示例",
)


def _build_context(state: DesignerState) -> str:
    parts: list[str] = []
    for key, label in (
        ("focus", "设计方向"),
        ("target_role", "目标岗位"),
        ("target_company", "目标公司"),
        ("user_background", "候选人背景"),
    ):
        value = state.get(key)
        if value:
            parts.append(f"{label}：{value}")
    profile = state.get("candidate_profile") or {}
    if profile:
        parts.append(
            "候选人画像："
            f"{profile.get('latest_level', 'unknown')}；"
            f"信号={', '.join(profile.get('latent_signals') or []) or '无'}"
        )
    report = state.get("evaluator_report") or {}
    if report.get("report_text"):
        parts.append(f"评估专家建议：{report['report_text']}")
    scoring = report.get("scoring") or {}
    if scoring.get("missing_dimensions"):
        parts.append(f"缺失维度：{', '.join(scoring.get('missing_dimensions') or [])}")
    previous = [q for q in state.get("previous_questions", []) if q]
    if previous:
        parts.append("已问过的问题：\n" + "\n".join(f"- {q}" for q in previous[-8:]))
    jd_context = state.get("jd_context") or {}
    if jd_context:
        parts.append(f"JD 上下文：{jd_context}")
    return "\n".join(parts)


def _prepared_question(state: DesignerState) -> dict[str, Any] | None:
    if state.get("focus") not in {"new_question", "ask_question", "next_question"}:
        return None
    prepared = state.get("prepared_questions") or []
    idx = state.get("current_question_index", 0)
    if prepared and idx < len(prepared):
        item = prepared[idx]
        return {
            "question_text": str(item.get("question", "")),
            "question_category": str(item.get("category") or "technical"),
            "focus_area": str(item.get("focus_area") or item.get("source") or "prepared"),
            "source": "prepared",
        }
    return None


async def design(state: DesignerState) -> DesignerState:
    prepared = _prepared_question(state)
    if prepared:
        return cast(DesignerState, {**dict(state), **prepared})

    context = _build_context(state)
    try:
        model = _chat_model(fast=True).with_structured_output(_DesignedQuestion)
        out = await model.ainvoke(
            [
                SystemMessage(content=DESIGNER_SYSTEM_PROMPT.format(context=context)),
                *[m for m in state.get("messages", []) if isinstance(m, BaseMessage)][-8:],
            ]
        )
        if isinstance(out, _DesignedQuestion):
            question_text = out.question_text.strip()
            category = out.question_category or "technical"
            focus_area = out.focus_area or state.get("focus", "")
        else:
            question_text = ""
            category = "technical"
            focus_area = state.get("focus", "")
    except Exception as exc:
        log.warning("designer_agent_llm_failed", error=str(exc))
        question_text = ""
        category = "technical"
        focus_area = state.get("focus", "")

    if not question_text:
        focus = state.get("focus") or "项目实践"
        question_text = f"请结合一个具体项目，说明你在{focus}上做过的关键技术决策和取舍。"

    return cast(DesignerState, {
        **dict(state),
        "question_text": question_text,
        "question_category": category,
        "focus_area": focus_area,
        "source": "llm",
    })


def _ngrams(text: str, n: int = 4) -> set[str]:
    t = text.strip().lower().replace(" ", "")
    return {t[i : i + n] for i in range(len(t) - n + 1)} if len(t) >= n else set()


def _is_repeated(question: str, previous: list[str]) -> bool:
    q_grams = _ngrams(question)
    if not q_grams:
        return False
    for prev in previous:
        p_grams = _ngrams(prev)
        if not p_grams:
            continue
        overlap = len(q_grams & p_grams) / max(len(q_grams | p_grams), 1)
        if overlap >= 0.6:
            return True
    return False


async def validate(state: DesignerState) -> DesignerState:
    question = state.get("question_text", "").strip()
    previous = state.get("previous_questions") or []
    if state.get("source") != "prepared":
        if any(pattern in question for pattern in GENERIC_PATTERNS) or _is_repeated(question, previous):
            focus = state.get("focus") or state.get("focus_area") or "当前回答中的薄弱点"
            question = f"围绕{focus}，请给出一个真实项目里的约束条件、你的方案选择，以及最终效果数据。"
        if "？" not in question and "?" not in question:
            question = question.rstrip("。") + "？"
    return cast(DesignerState, {**dict(state), "question_text": question})


async def respond_to_chief(state: DesignerState) -> DesignerState:
    output = {
        "question_text": state.get("question_text", ""),
        "question_category": state.get("question_category", "technical"),
        "focus_area": state.get("focus_area", state.get("focus", "")),
        "source": state.get("source", "llm"),
    }
    return cast(DesignerState, {**dict(state), "output": output})


def _ensure_question_mark(text: str) -> str:
    if "？" in text or "?" in text:
        return text
    return text.rstrip("。") + "？"


async def design_dual(state: DesignerState) -> DesignerState:
    """并行模式：一次 LLM 调用同时生成追问和新题两个方案。"""
    prepared = _prepared_question(cast(DesignerState, {**dict(state), "focus": "new_question"}))
    context = _build_context(state)
    followup_question = ""
    new_question = str((prepared or {}).get("question_text") or "")
    new_question_source = "prepared" if prepared else "llm"
    try:
        model = _chat_model(fast=True).with_structured_output(_DesignerDualOutput)
        out = await model.ainvoke(
            [
                SystemMessage(content=DESIGNER_DUAL_SYSTEM_PROMPT.format(context=context)),
                *[m for m in state.get("messages", []) if isinstance(m, BaseMessage)][-8:],
            ]
        )
        if isinstance(out, _DesignerDualOutput):
            followup_question = out.followup_question.strip()
            if not new_question:
                new_question = out.new_question.strip()
    except Exception as exc:
        log.warning("designer_dual_llm_failed", error=str(exc))

    focus = state.get("focus") or "当前回答中的薄弱点"
    role = state.get("target_role") or "该岗位"
    if not followup_question:
        followup_question = f"围绕{focus}，请结合真实项目说明你的约束条件、方案选择和最终效果数据。"
    if not new_question:
        new_question = f"请分享一个在{role}工作中遇到的技术挑战，以及你是如何解决的。"

    dual_output = {
        "followup_question": _ensure_question_mark(followup_question),
        "new_question": _ensure_question_mark(new_question),
        "followup_source": "llm",
        "new_question_source": new_question_source,
        "source": new_question_source,
    }
    return cast(DesignerState, {**dict(state), "dual_output": dual_output})
