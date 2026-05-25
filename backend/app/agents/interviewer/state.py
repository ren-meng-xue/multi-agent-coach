"""LangGraph state for the single interviewer agent."""
from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

InterviewStage = Literal["opening", "briefing", "interview", "closing"]


class InterviewState(TypedDict, total=False):
    """Graph state shared by interviewer nodes."""

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
    opening_complete: bool
    decision_action: str
    decision_reason: str
    followup_question: str
    report: dict[str, Any]
    briefing_intent: Literal["continue", "change_info", "not_ready"]

