"""Node functions for the multi-agent interviewer LangGraph."""
from __future__ import annotations

import asyncio
from typing import Any, Literal, cast

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

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
from app.agents.interviewer.state import CandidateProfile, InterviewState, TurnEvaluation
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.candidate_memory import upsert_candidate_memory

log = get_logger("app.agents.interviewer.nodes")

_RETRYABLE = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)

_retry_llm = retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    reraise=True,
)


# ─────────────────────────────────────────────
# 模型与工具
# ─────────────────────────────────────────────

def _chat_model(*, fast: bool = False, streaming: bool = False) -> ChatOpenAI:
    """构造一次 LLM 客户端。fast=True 用于 master 等延迟敏感节点。"""
    settings = get_settings()
    model_name = getattr(settings, "openai_model_chat_fast", settings.openai_model_chat) if fast else settings.openai_model_chat
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
    if state.get("resume_text"):
        context_parts.append(f"【候选人个人简历内容】：\n{state['resume_text']}")
    q_count = state.get("question_count", 0)
    q_total = state.get("total_questions", 5)
    if q_count > 0:
        context_parts.append(f"当前进度：第 {q_count} 题 / 共 {q_total} 题")
    qa_bank_items = state.get("qa_bank_items")
    if qa_bank_items:
        sections: dict[str, list[str]] = {"technical": [], "hr": [], "project": []}
        cat_labels = {"technical": "[技术题]", "hr": "[HR题]", "project": "[项目讲解]"}
        for item in qa_bank_items:
            cat = item.get("category", "technical")
            if cat in sections:
                sections[cat].append(
                    f"Q: {item['question']} / A（参考）: {item['model_answer']}"
                )
        block_lines = [
            "【用户已准备的题目库】",
            "以下题目请优先从中选取，覆盖整场面试：",
        ]
        for cat, label in cat_labels.items():
            if sections[cat]:
                block_lines.append(label)
                block_lines.extend(sections[cat])
        context_parts.append("\n".join(block_lines))
    if not context_parts:
        return messages
    summary = "【当前已确定的面试背景信息】：\n" + "\n".join(context_parts)
    return [SystemMessage(content=summary)] + messages


async def _generate_text(system_prompt: str, state: InterviewState) -> str:
    chunks: list[str] = []
    model = _chat_model(streaming=True).with_config(tags=["interviewer_answer_stream"])
    messages = _state_messages(state) + [SystemMessage(content=system_prompt)]
    async for chunk in model.astream(messages):
        chunks.append(_content_to_text(chunk.content))
    return "".join(chunks).strip()


# ─────────────────────────────────────────────
# 节点函数
# ─────────────────────────────────────────────

async def load_context_node(state: InterviewState) -> InterviewState:
    """Normalize defaults before master scheduling."""
    question_count = state.get("question_count", 0)
    return {
        "stage": state.get("stage") or "interview",
        "question_count": question_count,
        "total_questions": state.get("total_questions", 5),
        "followup_count": state.get("followup_count", 0),
        "max_followups": state.get("max_followups", 2),
        "current_question_index": state.get("current_question_index", question_count),
        "turn_evaluations": state.get("turn_evaluations", []),
        "chief_iteration": 0,
        "chief_messages": [],
        "chief_thoughts": [],
        "chief_tool_results": [],
        "evaluator_report": None,
        "designer_output": None,
        "designer_dual_output": None,
    }


class _InterviewMasterDecision(BaseModel):
    chain: list[str] = []
    reason: str = ""
    # Phase 4+：追问朝哪个方向（空串表示无 focus）
    followup_focus: str = ""


CHAIN_NODES = {"evaluator", "followup", "ask_question", "closing"}
TERMINAL_NODES = {"followup", "ask_question", "closing"}
DEFAULT_FALLBACK_CHAIN = ["evaluator", "followup"]


def _build_master_context(state: InterviewState) -> str:
    parts: list[str] = []
    parts.append(f"题目进度：{state.get('question_count', 0)} / {state.get('total_questions', 5)}")
    parts.append(f"当题追问次数：{state.get('followup_count', 0)} / {state.get('max_followups', 2)}")
    if state.get("target_role"):
        parts.append(f"目标岗位：{state['target_role']}")

    profile = state.get("candidate_profile") or {}
    if profile.get("latest_level"):
        parts.append(f"候选人画像：{profile['latest_level']}；已识别信号：{', '.join(profile.get('latent_signals', [])[:5])}")

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

    # 0. 增加：硬编码终止意图识别（作为 LLM 兜底）
    last_user_msg = ""
    for m in reversed(state.get("messages", [])):
        if getattr(m, "type", "") == "human":
            last_user_msg = str(getattr(m, "content", ""))
            break
    termination_keywords = [
        "结束", "结束吧", "结束面试", "结束了", "到此为止",
        "不面了", "不想面了", "不想继续", "我说完了", "我答完了",
        "够了", "算了", "停止", "退出", "退出面试", "再见", "拜拜",
    ]
    # 如果用户消息很短且包含关键词，强制进入 closing
    if any(kw in last_user_msg for kw in termination_keywords) and len(last_user_msg) < 15:
        log.info("master_chain_forced_by_termination_keyword", msg=last_user_msg)
        return ["closing"]

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

    # 2.5 当前题追问达到上限后必须推进流程，不能继续在同一题内深挖。
    if followup_count >= max_followups:
        forced = ["closing"] if question_count >= total_questions else ["evaluator", "ask_question"]
        if chain != forced:
            log.warning("master_chain_forced_after_max_followups", original=chain, fixed=forced)
        return forced

    # 3. 过滤非法节点 + 去空
    cleaned = [n for n in chain if n in CHAIN_NODES]
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
    # 若为首轮启动，跳过 LLM 复杂推理，直接输出固定意图
    if state.get("question_count", 0) == 0:
        # 首轮自动启动直接跳过真实 LLM 推理，由外层流生成器（stream_interviewer_turn_events）
        # 静态推送首轮思维链，从而省下 1 次 LLM 调用
        return {
            **state,
            "chain": ["ask_question"],
            "master_reason": "首轮自动启动",
        }

    context = _build_master_context(state)

    try:
        # 并行执行：Phase 1 负责流式推送 bullet，Phase 2 负责结构化输出
        # 虽然这会消耗 2x token，但能显著降低 master 节点的总延迟
        results = await asyncio.gather(
            _master_phase1_stream(context),
            _master_phase2_decide(context),
            return_exceptions=True
        )
        
        if isinstance(results[1], Exception):
            log.error("master_phase2_failed", error=str(results[1]))
            decision = _InterviewMasterDecision(chain=[], reason="Phase 2 failed")
        else:
            decision = cast(_InterviewMasterDecision, results[1])
        
        chain = list(decision.chain)
        reason = decision.reason
        followup_focus = decision.followup_focus
    except Exception as exc:
        log.error("master_node_unexpected_failure", error=str(exc))
        chain = []
        reason = "Master fallback"
        followup_focus = ""

    final_chain = _enforce_chain(chain, state)

    log.info("master_done", chain=final_chain, reason=reason)
    return {
        **state,
        "chain": final_chain,
        "master_reason": reason,
        "followup_focus": followup_focus,
    }


class _EvaluatorScoring(BaseModel):
    bullets: list[str] = []
    technical_depth: float = 5.0
    quantified_results: float = 5.0
    failure_tradeoffs: float = 5.0
    structure: float = 5.0
    summary_score: float = 5.0
    # Phase 4+：候选人建模 + 隐含信号
    candidate_level: Literal["beginner", "junior", "mid", "senior"] = "junior"
    latent_signals: list[str] = []
    missing_dimensions: list[str] = []
    followup_would_help: bool = True
    is_repeated_answer: bool = False


def _build_evaluator_context(state: InterviewState) -> str:
    """改：保留最近 N 轮上下文 + 候选人画像。"""
    MAX_TURNS = 8  # 最近 8 条消息（约 4 轮一问一答），token 上限兜底
    msgs = state.get("messages", [])[-MAX_TURNS:]
    transcript = []
    for m in msgs:
        role = "面试官" if getattr(m, "type", "") == "ai" else "候选人"
        text = str(getattr(m, "content", ""))[:400]
        transcript.append(f"{role}：{text}")

    profile = state.get("candidate_profile") or {}
    signals_so_far = profile.get("latent_signals") or []

    parts = []
    if state.get("target_role"):
        parts.append(f"目标岗位：{state['target_role']}")
    if signals_so_far:
        parts.append(f"已识别的隐含信号：{', '.join(signals_so_far[:10])}")
    parts.append("【最近对话】")
    parts.extend(transcript)
    return "\n".join(parts)


async def _evaluator_reason_stream(context: str) -> None:
    model = _chat_model(streaming=True).with_config(tags=["evaluator_token_stream"])
    prompt = EVALUATOR_REASONING_PROMPT.format(context=context)
    async for _ in model.astream([SystemMessage(content=prompt)]):
        pass


@_retry_llm
async def _evaluator_score(context: str) -> _EvaluatorScoring:
    model = _chat_model(fast=True).with_structured_output(_EvaluatorScoring)
    prompt = EVALUATOR_SCORING_PROMPT.format(context=context)
    out = await model.ainvoke([SystemMessage(content=prompt)])
    if isinstance(out, _EvaluatorScoring):
        return out
    return _EvaluatorScoring()


async def evaluator_node(state: InterviewState) -> InterviewState:
    context = _build_evaluator_context(state)
    try:
        # 并行执行：流式推送点评 bullet 和 深度打分
        results = await asyncio.gather(
            _evaluator_reason_stream(context),
            _evaluator_score(context),
            return_exceptions=True
        )
        
        if isinstance(results[1], Exception):
            log.error("evaluator_score_failed", error=str(results[1]))
            return {**state, "turn_evaluations": list(state.get("turn_evaluations", []))}
        scoring = cast(_EvaluatorScoring, results[1])
    except Exception as exc:
        log.error("evaluator_node_unexpected_failure", error=str(exc))
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
        # Phase 4+ 新增
        "candidate_level": scoring.candidate_level,
        "latent_signals": list(scoring.latent_signals),
        "missing_dimensions": list(scoring.missing_dimensions),
        "followup_would_help": scoring.followup_would_help,
        "is_repeated_answer": scoring.is_repeated_answer,
    }
    updated = list(state.get("turn_evaluations", []))
    updated.append(entry)

    # 累积 candidate_profile
    old_profile = state.get("candidate_profile") or {}
    old_signals = old_profile.get("latent_signals") or []
    new_signals = list(dict.fromkeys(old_signals + list(scoring.latent_signals)))[:20]
    new_profile: CandidateProfile = {
        "latest_level": scoring.candidate_level,
        "latent_signals": new_signals,
        "last_updated_turn": state.get("question_count", 0),
    }

    # Phase 5: 持久化候选人画像到长期记忆 (每轮评估后同步)
    db = state.get("db")
    user_id = state.get("user_id")
    if user_id and hasattr(db, "execute"):
        try:
            from uuid import UUID

            from sqlalchemy.ext.asyncio import AsyncSession

            if not isinstance(db, AsyncSession):
                return {
                    **state,
                    "turn_evaluations": updated,
                    "candidate_profile": new_profile,
                }

            raw_sid = state.get("session_id")
            session_id = UUID(str(raw_sid)) if raw_sid else None

            await upsert_candidate_memory(
                db,
                user_id,
                latest_level=scoring.candidate_level,
                latent_signals=list(scoring.latent_signals),
                weakness_tags=list(scoring.missing_dimensions),
                session_id=session_id,
            )
            # log.debug("evaluator_node_memory_synced", user_id=user_id)
        except Exception as exc:
            log.warning("evaluator_node_memory_sync_failed", error=str(exc))

    log.info("evaluator_done", summary_score=scoring.summary_score)
    return {**state, "turn_evaluations": updated, "candidate_profile": new_profile}


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

    model = _chat_model().with_structured_output(_ReportTextOutput)
    history = list(state.get("messages", []))

    # 将系统提示词置于首位，数据上下文置于末尾（HumanMessage）
    messages = [
        SystemMessage(content=REPORT_AGGREGATE_SYSTEM_PROMPT),
        *history,
        HumanMessage(content=f"【评分上下文】：\n{score_block}\n\n【每轮要点摘要】：\n{bullet_block}")
    ]

    out = await model.ainvoke(messages)
    if isinstance(out, _ReportTextOutput):
        return out
    return _ReportTextOutput()


@_retry_llm
async def _report_fallback_full_eval(state: InterviewState) -> ReportOutput:
    model = _chat_model().with_structured_output(ReportOutput)
    messages = [
        SystemMessage(content=REPORT_FALLBACK_SYSTEM_PROMPT),
        *_state_messages(state),
        HumanMessage(content="请基于以上面试对话，生成最终评估报告。")
    ]
    out = await model.ainvoke(messages)
    if isinstance(out, ReportOutput):
        return out
    return ReportOutput(
        overall_score=0.0,
        technical_depth=0.0, quantified_results=0.0,
        failure_tradeoffs=0.0, structure=0.0,
        highlights=[], improvements=[], key_concepts=[], common_mistakes=[],
    )


def _average_dimensions(evals: list[TurnEvaluation]) -> dict[str, float]:
    n = max(len(evals), 1)
    dims = ("technical_depth", "quantified_results", "failure_tradeoffs", "structure")
    totals = dict.fromkeys(dims, 0.0)
    for ev in evals:
        for dim in dims:
            value = ev.get(dim, 0.0)
            totals[dim] += float(value) if isinstance(value, int | float | str) else 0.0
    return {dim: totals[dim] / n for dim in dims}


def _report_output_to_dict(out: Any) -> dict[str, Any]:
    if hasattr(out, "model_dump"):
        dumped = out.model_dump()
        if isinstance(dumped, dict):
            return dumped
    fields = (
        "overall_score",
        "technical_depth",
        "quantified_results",
        "failure_tradeoffs",
        "structure",
        "highlights",
        "improvements",
        "key_concepts",
        "common_mistakes",
    )
    return {field: getattr(out, field) for field in fields}


async def generate_prepared_question_reply(question_text: str, state: InterviewState) -> str:
    target_role = state.get("target_role")
    question_count = state.get("question_count", 0)
    if question_count <= 1:
        prefix = f"我们先从「{target_role}」相关的一道题开始。" if target_role else "我们先从第一道题开始。"
        return f"{prefix}\n\n{question_text}"

    # Q4-1: 增加主问题之间的过渡语，避免跳跃
    import random
    transitions = [
        "关于这块我了解了。接下来，我们聊聊另一个话题：",
        "好的。那我们换个方向，来看下一道题：",
        "明白。我们继续深入，看这个问题：",
        "很有参考价值。下面我们来看：",
    ]
    prefix = random.choice(transitions)
    return f"{prefix}\n\n{question_text}"


async def ask_question_node(state: InterviewState) -> InterviewState:
    """出新一题（优先用 prepared_questions）。"""
    next_question_count = state.get("question_count", 0) + 1
    prepared = state.get("prepared_questions") or []
    idx = state.get("current_question_index", state.get("question_count", 0))

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
    focus = state.get("followup_focus", "")
    last_eval = (state.get("turn_evaluations") or [{}])[-1]
    latent = last_eval.get("latent_signals", []) or []
    missing = last_eval.get("missing_dimensions", []) or []

    extra_ctx = (
        f"\n【本轮追问信号】\n"
        f"- followup_focus: {focus or '无'}\n"
        f"- latent_signals: {', '.join(latent) or '无'}\n"
        f"- missing_dimensions: {', '.join(missing) or '无'}"
    )

    text = await _generate_text(FOLLOWUP_SYSTEM_PROMPT + extra_ctx, state)
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
    evals = state.get("turn_evaluations", [])

    if not evals:
        log.warning("report_fallback_no_turn_evals")
        try:
            out = await _report_fallback_full_eval(state)
            return {"report": _report_output_to_dict(out)}
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

    # Phase 5: 持久化候选人画像到长期记忆
    db = state.get("db")
    user_id = state.get("user_id")
    if user_id and hasattr(db, "execute"):  # 简单的 AsyncSession 运行时检查
        from uuid import UUID

        from sqlalchemy.ext.asyncio import AsyncSession

        if isinstance(db, AsyncSession):
            try:
                profile = state.get("candidate_profile") or {}
                # 聚合所有轮次的缺失维度作为弱点标签
                weakness_tags = []
                for ev in evals:
                    for dim in ev.get("missing_dimensions", []):
                        if dim not in weakness_tags:
                            weakness_tags.append(dim)

                raw_sid = state.get("session_id")
                session_id = UUID(str(raw_sid)) if raw_sid else None

                await upsert_candidate_memory(
                    db,
                    user_id,
                    latest_level=profile.get("latest_level"),
                    latent_signals=profile.get("latent_signals") or [],
                    weakness_tags=weakness_tags,
                    session_id=session_id,
                )
                log.info("report_node_memory_persisted", user_id=user_id)
            except Exception as exc:
                # 失败不阻塞报告产出
                log.warning("report_node_memory_persist_failed", error=str(exc), user_id=user_id)

    return {"report": report}
