"""Node functions for the multi-agent interviewer LangGraph."""
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.agents.interviewer.prompts import (
    CLOSING_SYSTEM_PROMPT,
    FOLLOWUP_SYSTEM_PROMPT,
    QUESTION_SYSTEM_PROMPT,
)
from app.agents.interviewer.state import InterviewState
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.agents.interviewer.nodes")


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
