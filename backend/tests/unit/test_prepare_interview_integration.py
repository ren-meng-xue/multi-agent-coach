"""Prepare → interview 接入点的轻量单元测试。"""
import pytest

from app.agents.interviewer.graph import route_after_master
from app.agents.interviewer.nodes import load_context_node, master_node
from app.agents.interviewer.state import InterviewState


@pytest.mark.asyncio
async def test_load_context_defaults_to_interview_stage():
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
    }
    result = await load_context_node(state)
    assert result["stage"] == "interview"
    assert result["question_count"] == 0
    assert result["turn_evaluations"] == []


@pytest.mark.asyncio
async def test_first_turn_with_prepared_questions_forces_ask_question(monkeypatch):
    """Phase 3 准备题接入后，首轮由 master 强制进入 ask_question。"""

    async def fake_phase1(context: str) -> None:
        return None

    async def fake_phase2(context: str):
        class Decision:
            chain = ["evaluator", "followup"]
            reason = "fake"

        return Decision()

    monkeypatch.setattr("app.agents.interviewer.nodes._master_phase1_stream", fake_phase1)
    monkeypatch.setattr("app.agents.interviewer.nodes._master_phase2_decide", fake_phase2)

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
        "messages": [],
    }
    result = await master_node(state)
    assert result["chain"] == ["ask_question"]
    assert route_after_master(result) == "ask_question"
