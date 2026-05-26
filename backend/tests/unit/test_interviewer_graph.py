"""interviewer graph 重构后的占位测试。详细 chain 路由测试见 test_interviewer_chain_routing.py。"""
from app.agents.interviewer.graph import (
    CHAIN_NODES,
    build_interviewer_graph,
    route_after_master,
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
