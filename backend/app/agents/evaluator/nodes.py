"""Node functions for the Evaluator Agent."""
from __future__ import annotations

from typing import Any, cast

from langchain_core.messages import SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.evaluator.prompts import EVALUATOR_REPORT_PROMPT
from app.agents.evaluator.state import EvaluatorState
from app.agents.interviewer.nodes import (
    _chat_model,
    _content_to_text,
    _evaluator_score,
    _EvaluatorScoring,
)
from app.agents.interviewer.state import CandidateProfile, TurnEvaluation
from app.core.logging import get_logger
from app.services.candidate_memory import upsert_candidate_memory

log = get_logger("app.agents.evaluator.nodes")


def _turn_evaluation_from_scoring(
    scoring: _EvaluatorScoring,
    *,
    question_index: int,
    followup_index: int,
) -> TurnEvaluation:
    return {
        "question_index": question_index,
        "followup_index": followup_index,
        "bullets": list(scoring.bullets),
        "technical_depth": scoring.technical_depth,
        "quantified_results": scoring.quantified_results,
        "failure_tradeoffs": scoring.failure_tradeoffs,
        "structure": scoring.structure,
        "summary_score": scoring.summary_score,
        "candidate_level": scoring.candidate_level,
        "latent_signals": list(scoring.latent_signals),
        "missing_dimensions": list(scoring.missing_dimensions),
        "followup_would_help": scoring.followup_would_help,
        "is_repeated_answer": scoring.is_repeated_answer,
    }


def _updated_profile(
    existing_profile: CandidateProfile | None,
    scoring: _EvaluatorScoring,
    *,
    question_index: int,
) -> CandidateProfile:
    old_profile = existing_profile or {}
    old_signals = old_profile.get("latent_signals") or []
    new_signals = list(dict.fromkeys(old_signals + list(scoring.latent_signals)))[:20]
    return {
        "latest_level": scoring.candidate_level,
        "latent_signals": new_signals,
        "last_updated_turn": question_index,
    }


def _build_context(state: EvaluatorState) -> str:
    parts: list[str] = []
    if state.get("target_role"):
        parts.append(f"目标岗位：{state['target_role']}")
    existing = state.get("existing_profile") or {}
    if existing.get("latest_level"):
        parts.append(f"既有画像等级：{existing['latest_level']}")
    if existing.get("latent_signals"):
        parts.append(f"既有信号：{', '.join(existing.get('latent_signals', [])[:10])}")
    if state.get("conversation_context"):
        parts.append("【最近对话】")
        parts.append(state["conversation_context"])
    if state.get("latest_answer"):
        parts.append("【候选人最新回答】")
        parts.append(state["latest_answer"][:1200])
    return "\n".join(parts)


async def analyze_answer(state: EvaluatorState) -> EvaluatorState:
    context = _build_context(state)
    try:
        scoring = await _evaluator_score(context)
    except Exception as exc:
        log.error("evaluator_agent_score_failed", error=str(exc))
        scoring = _EvaluatorScoring()

    entry = _turn_evaluation_from_scoring(
        scoring,
        question_index=state.get("question_index", 0),
        followup_index=state.get("followup_index", 0),
    )
    profile = _updated_profile(
        state.get("existing_profile"),
        scoring,
        question_index=state.get("question_index", 0),
    )
    return cast(EvaluatorState, {**dict(state), "scoring": entry, "updated_profile": profile})


async def update_profile(state: EvaluatorState) -> EvaluatorState:
    db = state.get("db")
    user_id = state.get("user_id")
    scoring = state.get("scoring") or {}
    if user_id and isinstance(db, AsyncSession):
        try:
            from uuid import UUID

            raw_sid = state.get("session_id")
            session_id = UUID(str(raw_sid)) if raw_sid else None
            await upsert_candidate_memory(
                db,
                user_id,
                latest_level=scoring.get("candidate_level"),
                latent_signals=list(scoring.get("latent_signals") or []),
                weakness_tags=list(scoring.get("missing_dimensions") or []),
                session_id=session_id,
            )
        except Exception as exc:
            log.warning("evaluator_agent_memory_sync_failed", error=str(exc), user_id=user_id)
    return state


def _fallback_report_text(scoring: dict[str, Any]) -> str:
    score = scoring.get("summary_score", 5.0)
    missing = ", ".join(scoring.get("missing_dimensions") or [])
    signals = ", ".join(scoring.get("latent_signals") or [])
    if missing:
        return f"本轮回答总分约 {score}，已识别信号：{signals or '无'}。主要缺口是 {missing}，建议围绕缺口做一次具体追问。"
    return f"本轮回答总分约 {score}，已识别信号：{signals or '无'}。没有明显缺失维度，建议进入下一题或在题数已满时收尾。"


async def respond_to_chief(state: EvaluatorState) -> EvaluatorState:
    scoring = dict(state.get("scoring") or {})
    context = _build_context(state)
    try:
        model = _chat_model(fast=True)
        prompt = EVALUATOR_REPORT_PROMPT.format(context=context, scoring=scoring)
        out = await model.ainvoke([SystemMessage(content=prompt)])
        report_text = _content_to_text(out.content).strip()
    except Exception as exc:
        log.warning("evaluator_agent_report_failed", error=str(exc))
        report_text = _fallback_report_text(scoring)

    report: dict[str, Any] = {
        "scoring": scoring,
        "updated_profile": dict(state.get("updated_profile") or {}),
        "report_text": report_text,
    }
    return cast(EvaluatorState, {**dict(state), "report_text": report_text, "report": report})
