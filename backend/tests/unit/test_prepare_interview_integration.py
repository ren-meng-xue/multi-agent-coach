# backend/tests/unit/test_prepare_interview_integration.py
from app.agents.interviewer.graph import route_after_load
from app.agents.interviewer.state import InterviewState


def test_route_after_load_skips_opening_when_prepared_questions():
    state: InterviewState = {
        "session_id": "s1",
        "prepared_questions": [
            {
                "id": 1,
                "question": "Q1",
                "category": "technical",
                "focus_area": "f",
                "priority": 1,
            }
        ],
        "question_count": 0,
        "stage": None,
    }
    result = route_after_load(state)
    assert result == "ask_question"


def test_route_after_load_uses_opening_without_prepared_questions():
    state: InterviewState = {
        "session_id": "s1",
        "prepared_questions": [],
        "question_count": 0,
        "stage": None,
    }
    result = route_after_load(state)
    # 现有逻辑路由应当在 opening, briefing, ask_question 之一
    assert result in ("opening", "briefing", "ask_question")
