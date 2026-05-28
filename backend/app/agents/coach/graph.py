"""教练 Agent 子图组装。"""
from collections.abc import AsyncGenerator
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.coach.nodes import (
    load_memory_node,
    persist_node,
    plan_node,
    review_node,
)
from app.agents.coach.state import CoachState


def build_coach_graph():
    """组装线性教练子图：加载记忆 -> 复盘生成 -> 计划制定 -> 持久化。"""
    workflow = StateGraph(CoachState)
    
    workflow.add_node("load_memory", load_memory_node)
    workflow.add_node("review", review_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("persist", persist_node)
    
    workflow.set_entry_point("load_memory")
    workflow.add_edge("load_memory", "review")
    workflow.add_edge("review", "plan")
    workflow.add_edge("plan", "persist")
    workflow.add_edge("persist", END)
    
    return workflow.compile()

async def stream_coach_events(state: CoachState) -> AsyncGenerator[dict[str, Any], None]:
    """流式执行教练子图。"""
    graph = build_coach_graph()
    async for event in graph.astream(state, stream_mode="updates"):
        yield event
