"""State for the Evaluator Agent."""
from typing import Any, TypedDict

from app.agents.interviewer.state import CandidateProfile, TurnEvaluation


class EvaluatorState(TypedDict, total=False):
    session_id: str
    user_id: str
    target_role: str
    latest_answer: str
    conversation_context: str
    existing_profile: CandidateProfile | None
    question_index: int
    followup_index: int
    db: Any
    job_intel: dict[str, Any] | None

    scoring: TurnEvaluation
    updated_profile: CandidateProfile
    report_text: str
    report: dict[str, Any]
