"""Node functions for the multi-agent interviewer LangGraph."""
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage
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
)
from app.agents.interviewer.state import InterviewState, TurnEvaluation
from app.core.config import get_settings
from app.core.logging import get_logger

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
        elif not last_ai and getattr(m, "type", "") == "ai":
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
