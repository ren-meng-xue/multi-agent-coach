"""interviewer graph 重构后的占位测试。详细 chain 路由测试见 test_interviewer_chain_routing.py。"""
from unittest.mock import MagicMock, patch

import pytest

from app.agents.interviewer.graph import (
    CHAIN_NODES,
    build_interviewer_graph,
    route_after_master,
    stream_interviewer_turn_events,
)


def test_chain_nodes_exposes_master_subagents():
    """master 子 agent 池必须是 evaluator/followup/ask_question/closing 四者。"""
    assert {"evaluator", "followup", "ask_question", "closing"} == CHAIN_NODES


def test_route_after_master_empty_chain_fallback_to_followup():
    """空 chain 防御性 fallback。"""
    assert route_after_master({"chain": []}) == "followup"
    assert route_after_master({}) == "followup"


def test_route_after_master_uses_chain_head():
    assert route_after_master({"chain": ["evaluator", "followup"]}) == "evaluator"
    assert route_after_master({"chain": ["closing"]}) == "closing"


def test_route_after_master_unknown_node_falls_back_to_followup():
    assert route_after_master({"chain": ["nonexistent"]}) == "followup"


def test_build_interviewer_graph_does_not_error():
    """graph 编译本身不应抛错。"""
    g = build_interviewer_graph()
    assert g is not None


# ─────────────────────────────────────────────
# Phase 4+ SSE Payload 测试
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_events_evaluator_done_payload():
    """验证 node_done payload 包含 candidate_level 等新字段。"""
    state = {"session_id": "test_session", "question_count": 1}
    
    # Mock graph.astream_events
    mock_event = {
        "event": "on_chain_end",
        "name": "evaluator",
        "metadata": {"langgraph_node": "evaluator"},
        "data": {
            "output": {
                "turn_evaluations": [{
                    "summary_score": 8.5,
                    "candidate_level": "senior",
                    "latent_signals": ["architecture"],
                    "missing_dimensions": ["quantification"]
                }]
            }
        }
    }
    
    async def mock_astream(*args, **kwargs):
        yield mock_event
        yield {"event": "on_chain_end", "name": "LangGraph", "data": {"output": {}}}

    mock_graph = MagicMock()
    mock_graph.astream_events.side_effect = mock_astream
    
    with patch("app.agents.interviewer.graph.get_interviewer_graph", return_value=mock_graph):
        events = []
        async for ev in stream_interviewer_turn_events(state):
            events.append(ev)
            
        node_done = next(e for e in events if e["event"] == "node_done")
        data = node_done["data"]
        assert data["node"] == "evaluator"
        assert data["candidate_level"] == "senior"
        assert data["latent_signals"] == ["architecture"]
        assert data["missing_dimensions"] == ["quantification"]

@pytest.mark.asyncio
async def test_stream_events_master_done_payload():
    """验证 master node_done payload 包含 followup_focus。"""
    state = {"session_id": "test_session", "question_count": 1}
    
    mock_event = {
        "event": "on_chain_end",
        "name": "master",
        "metadata": {"langgraph_node": "master"},
        "data": {
            "output": {
                "chain": ["evaluator", "followup"],
                "followup_focus": "tradeoff"
            }
        }
    }
    
    async def mock_astream(*args, **kwargs):
        yield mock_event
        yield {"event": "on_chain_end", "name": "LangGraph", "data": {"output": {}}}

    mock_graph = MagicMock()
    mock_graph.astream_events.side_effect = mock_astream
    
    with patch("app.agents.interviewer.graph.get_interviewer_graph", return_value=mock_graph):
        events = []
        async for ev in stream_interviewer_turn_events(state):
            events.append(ev)
            
        node_done = next(e for e in events if e["event"] == "node_done")
        assert node_done["data"]["followup_focus"] == "tradeoff"
