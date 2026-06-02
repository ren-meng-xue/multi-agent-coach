"""State for the Question Designer Agent."""
from typing import Any, TypedDict

from app.agents.interviewer.state import CandidateProfile


class DesignerState(TypedDict, total=False):
    focus: str
    target_role: str
    target_company: str
    user_background: str
    candidate_profile: CandidateProfile
    jd_context: dict[str, Any] | None
    previous_questions: list[str]
    prepared_questions: list[dict[str, Any]]
    current_question_index: int
    evaluator_report: dict[str, Any] | None
    messages: list[Any]

    question_text: str
    question_category: str
    focus_area: str
    source: str
    output: dict[str, Any]
    dual_output: dict[str, Any]
