"""Node functions for the interviewer LangGraph."""
from typing import Any, Literal

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.agents.interviewer.prompts import (
    BRIEFING_INTENT_SYSTEM_PROMPT,
    BRIEFING_SYSTEM_PROMPT,
    CLOSING_SYSTEM_PROMPT,
    DECIDE_SYSTEM_PROMPT,
    NOT_READY_SYSTEM_PROMPT,
    OPENING_INFO_SYSTEM_PROMPT,
    OPENING_SYSTEM_PROMPT,
    QUESTION_SYSTEM_PROMPT,
    REPORT_SYSTEM_PROMPT,
)
from app.agents.interviewer.state import InterviewState
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.agents.interviewer.nodes")


class DecideNextOutput(BaseModel):
    """Structured output from decide_next."""

    action: Literal["followup", "next_question", "closing"]
    depth_analysis: str  # 分析当前话题的深挖价值：已覆盖哪些能力，还剩哪些值得挖掘的盲点
    reason: str
    followup_question: str = ""


class OpeningInfoOutput(BaseModel):
    """Structured opening information extracted from the conversation."""

    complete: bool
    target_role: str = ""
    target_company: str = ""
    user_background: str = ""
    missing_fields: list[Literal["target_role", "target_company", "user_background"]] = []


class BriefingIntentOutput(BaseModel):
    """Structured output for briefing stage user intent detection."""

    intent: Literal["continue", "change_info", "not_ready"]
    reason: str = ""



def _chat_model() -> ChatOpenAI:
    """Create a LangChain chat model using existing pydantic-settings config."""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model_chat,
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
    )


def _state_messages(state: InterviewState) -> list[BaseMessage]:
    """获取消息列表，并根据 state 中的背景信息注入上下文系统消息。"""
    messages = state.get("messages", [])
    
    # 构造上下文摘要
    context_parts = []
    if state.get("target_role"):
        context_parts.append(f"目标岗位：{state['target_role']}")
    if state.get("target_company"):
        context_parts.append(f"目标公司：{state['target_company']}")
    if state.get("user_background"):
        context_parts.append(f"项目背景/技术主题：{state['user_background']}")
    
    # 注入进度信息
    q_count = state.get("question_count", 0)
    q_total = state.get("total_questions", 6)
    if q_count > 0:
        context_parts.append(f"当前进度：第 {q_count} 题 / 共 {q_total} 题")
    
    if context_parts:
        # 将背景信息作为系统提示注入，确保节点 LLM 感知
        context_summary = "【当前已确定的面试背景信息】：\n" + "\n".join(context_parts)
        return [SystemMessage(content=context_summary)] + messages
        
    return messages


async def _generate_text(system_prompt: str, state: InterviewState) -> str:
    """Generate one assistant message from the current state."""
    chunks: list[str] = []
    model = _chat_model().with_config(tags=["interviewer_answer_stream"])
    # 将节点特定的指令放在最后，确保模型能够优先遵循最新节点的动作（如结束面试）
    messages = _state_messages(state) + [SystemMessage(content=system_prompt)]
    async for chunk in model.astream(messages):
        chunks.append(_content_to_text(chunk.content))
    return "".join(chunks).strip()


def _content_to_text(content: Any) -> str:
    """Convert LangChain message content chunks to plain text."""
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


async def generate_opening_reply(state: InterviewState) -> str:
    """Ask for target role/company/background before formal questions."""
    return await _generate_text(OPENING_SYSTEM_PROMPT, state)


async def generate_briefing_reply(state: InterviewState) -> str:
    """Generate the briefing message confirming role, rules and asking if ready."""
    return await _generate_text(BRIEFING_SYSTEM_PROMPT, state)


async def detect_briefing_intent(state: InterviewState) -> BriefingIntentOutput:
    """Detect candidate intent during the briefing stage."""
    model = _chat_model().with_structured_output(BriefingIntentOutput)
    output = await model.ainvoke(
        [*_state_messages(state), SystemMessage(content=BRIEFING_INTENT_SYSTEM_PROMPT)]
    )
    if isinstance(output, BriefingIntentOutput):
        return output
    log.warning("interviewer_briefing_intent_unexpected_output", output=str(output))
    return BriefingIntentOutput(intent="continue", reason="结构化分析结果异常，进入面试流程")


async def generate_not_ready_reply(state: InterviewState) -> str:
    """Generate a waiting reply when candidate is not ready."""
    return await _generate_text(NOT_READY_SYSTEM_PROMPT, state)


async def extract_opening_info(state: InterviewState) -> OpeningInfoOutput:
    """提取开场信息，若 state 中已存在关键信息则直接返回 True。"""
    # 优先检查 state 中是否已有预设信息
    target_role = state.get("target_role", "").strip()
    target_company = state.get("target_company", "").strip()
    user_background = state.get("user_background", "").strip()
    
    # 只要岗位或背景中有一项，就认为开场信息已足够开启面试（对应 prompt 中的逻辑）
    if target_role or user_background:
        return OpeningInfoOutput(
            complete=True,
            target_role=target_role,
            target_company=target_company,
            user_background=user_background,
        )

    # 若没有任何信息，再尝试从对话历史中抽取
    model = _chat_model().with_structured_output(OpeningInfoOutput)
    output = await model.ainvoke(
        [SystemMessage(content=OPENING_INFO_SYSTEM_PROMPT), *state.get("messages", [])]
    )
    if isinstance(output, OpeningInfoOutput):
        return output
    log.warning("interviewer_opening_info_unexpected_output", output=str(output))
    return OpeningInfoOutput(
        complete=False,
        missing_fields=["target_role", "target_company", "user_background"],
    )


async def generate_question_reply(state: InterviewState) -> str:
    """Generate the next formal interview question."""
    return await _generate_text(QUESTION_SYSTEM_PROMPT, state)


async def decide_next_action(state: InterviewState) -> DecideNextOutput:
    """Judge the latest answer and choose followup, next question, or closing."""
    # 硬性防护只作为最后的保险，防止无限追问（例如死循环）
    if state.get("question_count", 0) >= state.get("total_questions", 6) and state.get("followup_count", 0) >= state.get("max_followups", 5):
        return DecideNextOutput(
            action="closing",
            depth_analysis="已达到系统硬性上限",
            reason="安全退出"
        )

    model = _chat_model().with_structured_output(DecideNextOutput)
    output = await model.ainvoke([*_state_messages(state), SystemMessage(content=DECIDE_SYSTEM_PROMPT)])
    if isinstance(output, DecideNextOutput):
        return output
    log.warning("interviewer_decide_unexpected_output", output=str(output))
    return DecideNextOutput(
        action="next_question",
        depth_analysis="异常降级",
        reason="结构化判断结果异常，进入下一题"
    )


async def generate_closing_reply(state: InterviewState) -> str:
    """Generate a short closing message."""
    return await _generate_text(CLOSING_SYSTEM_PROMPT, state)


async def load_context_node(state: InterviewState) -> InterviewState:
    """Normalize defaults before routing."""
    return {
        "stage": state.get("stage") or "opening",
        "question_count": state.get("question_count", 0),
        "total_questions": state.get("total_questions", 6), # 包含开场自我介绍
        "followup_count": state.get("followup_count", 0),
        "max_followups": state.get("max_followups", 5), # 允许深度追问
        "opening_complete": state.get("opening_complete", False) or bool(
            state.get("target_role")
            or state.get("target_company")
            or state.get("user_background")
        ),
    }


async def opening_node(state: InterviewState) -> InterviewState:
    """Opening phase: collect interview direction."""
    info = await extract_opening_info(state)
    if info.complete:
        updated_state: InterviewState = {
            **state,
            "target_role": info.target_role.strip(),
            "target_company": info.target_company.strip(),
            "user_background": info.user_background.strip(),
        }
        briefing_msg = await generate_briefing_reply(updated_state)
        return {
            "stage": "briefing",
            "opening_complete": True,
            "target_role": info.target_role.strip(),
            "target_company": info.target_company.strip(),
            "user_background": info.user_background.strip(),
            "assistant_message": briefing_msg,
        }

    return {
        "stage": "opening",
        "opening_complete": False,
        "assistant_message": await generate_opening_reply(state),
    }


async def briefing_node(state: InterviewState) -> InterviewState:
    """Briefing phase: evaluate candidate ready intent, change direction, or wait."""
    intent_output = await detect_briefing_intent(state)
    intent = intent_output.intent

    if intent == "continue":
        return {
            "briefing_intent": "continue",
        }
    elif intent == "change_info":
        return {
            "stage": "opening",
            "opening_complete": False,
            "briefing_intent": "change_info",
            "target_role": "",
            "target_company": "",
            "user_background": "",
        }
    else:  # not_ready
        return {
            "stage": "briefing",
            "briefing_intent": "not_ready",
            "assistant_message": await generate_not_ready_reply(state),
        }



async def ask_question_node(state: InterviewState) -> InterviewState:
    """Ask the next formal interview question and reset per-question followups."""
    next_question_count = state.get("question_count", 0) + 1
    return {
        "stage": "interview",
        "question_count": next_question_count,
        "followup_count": 0,
        "assistant_message": await generate_question_reply({**state, "question_count": next_question_count}),
    }


async def decide_next_node(state: InterviewState) -> InterviewState:
    """Decide how to continue after a candidate answer."""
    decision = await decide_next_action(state)
    return {
        "decision_action": decision.action,
        "decision_reason": decision.reason,
        "followup_question": decision.followup_question,
    }


async def followup_node(state: InterviewState) -> InterviewState:
    """Ask a followup for the current question."""
    question = state.get("followup_question") or "请你再补充一个更具体的例子。"
    return {
        "stage": "interview",
        "followup_count": state.get("followup_count", 0) + 1,
        "assistant_message": question,
    }


async def closing_node(state: InterviewState) -> InterviewState:
    """Close the interview."""
    return {
        "stage": "closing",
        "assistant_message": await generate_closing_reply(state),
    }


class ReportOutput(BaseModel):
    """Structured interview assessment report."""

    overall_score: float
    technical_depth: float
    quantified_results: float
    failure_tradeoffs: float
    structure: float
    highlights: list[str]
    improvements: list[str]
    key_concepts: list[str]
    common_mistakes: list[str]


async def generate_report_output(state: InterviewState) -> ReportOutput | None:
    """Call LLM with structured output to generate interview assessment."""
    model = _chat_model().with_structured_output(ReportOutput)
    output = await model.ainvoke(
        [*_state_messages(state), SystemMessage(content=REPORT_SYSTEM_PROMPT)]
    )
    if isinstance(output, ReportOutput):
        return output
    return None


async def report_node(state: InterviewState) -> InterviewState:
    """面试结束后生成结构化评分报告。"""
    output = await generate_report_output(state)
    if output is None:
        log.warning("interviewer_report_unexpected_output")
        return {"report": {}}
    return {"report": output.model_dump()}
