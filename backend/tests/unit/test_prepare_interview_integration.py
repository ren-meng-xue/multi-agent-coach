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


@pytest.mark.asyncio
async def test_end_to_end_one_turn_emits_full_event_sequence(monkeypatch, db):
    """模拟一次完整 turn：master + evaluator + followup 节点都跑。"""
    from uuid import uuid4

    from app.services.interview_turn import stream_interview_turn

    test_user_id = f"user_{uuid4().hex}"

    async def fake_graph_events(state):
        yield {"event": "node_start", "data": {"node": "master", "label": "MASTER"}}
        yield {"event": "node_token", "data": {"node": "master", "text": "评估后追问"}}
        yield {"event": "node_done", "data": {"node": "master", "elapsed_ms": 120, "chain": ["evaluator", "followup"]}}
        yield {"event": "node_start", "data": {"node": "evaluator", "label": "评估"}}
        yield {"event": "node_token", "data": {"node": "evaluator", "text": "·覆盖CAP"}}
        yield {"event": "node_done", "data": {"node": "evaluator", "elapsed_ms": 220, "summary_score": 7.0}}
        yield {"event": "node_start", "data": {"node": "followup", "label": "面试官 · 追问"}}
        yield {"event": "token", "data": {"text": "QPS"}}
        yield {"event": "token", "data": {"text": "是多少？"}}
        yield {"event": "node_done", "data": {"node": "followup", "elapsed_ms": 800}}
        yield {"event": "final", "data": {
            "stage": "interview",
            "question_count": 1, "total_questions": 5,
            "followup_count": 1, "max_followups": 2,
            "target_role": "Test",
            "assistant_message": "QPS是多少？",
            "turn_evaluations": [{
                "question_index": 1, "followup_index": 0, "bullets": ["覆盖CAP"],
                "technical_depth": 7.0, "quantified_results": 4.0,
                "failure_tradeoffs": 6.5, "structure": 7.5, "summary_score": 6.25,
            }],
        }}

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events",
        fake_graph_events,
    )

    captured = []
    async for ev in stream_interview_turn(
        message="我用 CAP 解决",
        user_id=test_user_id,
        db=db,
    ):
        captured.append(ev)

    node_starts = [e for e in captured if e["event"] == "node_start"]
    node_dones = [e for e in captured if e["event"] == "node_done"]
    deltas = [e for e in captured if e["event"] == "delta"]
    assert {n["data"]["node"] for n in node_starts} == {"master", "evaluator", "followup"}
    assert any(d["data"].get("text") == "QPS" for d in deltas)
    master_done = next(d for d in node_dones if d["data"]["node"] == "master")
    assert master_done["data"]["chain"] == ["evaluator", "followup"]

