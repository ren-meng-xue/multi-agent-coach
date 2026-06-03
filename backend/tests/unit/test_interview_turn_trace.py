import pytest
from app.services.interview_turn import _build_turn_trace

def test_build_turn_trace_basic():
    node_events = [
        {"evt": "node_start", "data": {"node": "master", "label": "调度"}},
        {"evt": "node_token", "data": {"node": "master", "text": "思考"}},
        {"evt": "node_token", "data": {"node": "master", "text": "中"}},
        {"evt": "node_done", "data": {"node": "master", "elapsed_ms": 100}},
        {"evt": "node_start", "data": {"node": "evaluator", "label": "评估"}},
        {"evt": "node_done", "data": {"node": "evaluator", "elapsed_ms": 200, "summary_score": 8.5}},
    ]

    result = _build_turn_trace(
        node_events=node_events,
        question_count=1,
        is_opening=False
    )

    assert result["status"] == "done"
    assert result["turnIndex"] == 1
    assert result["summaryScore"] == 8.5
    assert len(result["nodes"]) == 2

    master_node = next(n for n in result["nodes"] if n["id"] == "master")
    assert master_node["status"] == "done"
    assert master_node["tokens"] == "思考中"
    assert master_node["elapsedMs"] == 100
    assert master_node["title"] == "分析表现，规划下一步"

    eval_node = next(n for n in result["nodes"] if n["id"] == "evaluator")
    assert eval_node["status"] == "done"
    assert eval_node["elapsedMs"] == 200

def test_build_turn_trace_empty():
    result = _build_turn_trace(
        node_events=[],
        question_count=0,
        is_opening=True
    )
    assert result is None

def test_build_turn_trace_no_done():
    node_events = [
        {"evt": "node_start", "data": {"node": "master", "label": "调度"}},
        {"evt": "node_token", "data": {"node": "master", "text": "思考"}},
    ]
    result = _build_turn_trace(
        node_events=node_events,
        question_count=1,
        is_opening=False
    )
    assert result["nodes"][0]["status"] == "running"
    assert result["nodes"][0]["tokens"] == "思考"

def test_build_turn_trace_assistant_message_fallback():
    node_events = [
        {"evt": "node_start", "data": {"node": "chief_think", "label": "思考"}},
        {"evt": "node_done", "data": {"node": "chief_think", "assistant_message": "已评价回答", "elapsed_ms": 50}},
        {"evt": "node_start", "data": {"node": "chief_respond", "label": "回复"}},
        {"evt": "node_done", "data": {"node": "chief_respond", "assistant_message": "请问您...", "elapsed_ms": 30}},
    ]
    result = _build_turn_trace(
        node_events=node_events,
        question_count=1,
        is_opening=False
    )
    
    think_node = next(n for n in result["nodes"] if n["id"] == "chief_think")
    assert think_node["tokens"] == "已评价回答"
    
    respond_node = next(n for n in result["nodes"] if n["id"] == "chief_respond")
    assert respond_node["tokens"] == "请问您..."
    assert respond_node["status"] == "done"
