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
    """流式执行教练子图（节点级更新）。"""
    graph = build_coach_graph()
    async for event in graph.astream(state, stream_mode="updates"):
        yield event


async def stream_coach_full_events(state: CoachState) -> AsyncGenerator[dict[str, Any], None]:
    """流式执行教练子图，包含节点更新和 LLM Token 流。"""
    graph = build_coach_graph()
    # 使用 v2 版本的 astream_events
    async for event in graph.astream_events(state, version="v2"):
        kind = event["event"]
        
        # 1. 节点完成更新
        if kind == "on_chain_stream" and event.get("metadata", {}).get("langgraph_node"):
            node_name = event["metadata"]["langgraph_node"]
            yield {"kind": "node_update", "node": node_name, "data": event["data"]["chunk"]}
            
        # 2. LLM Token 流
        elif kind == "on_chat_model_stream":
            tags = event.get("tags", [])
            if "coach_review_stream" in tags:
                content = event["data"]["chunk"].content
                if content:
                    yield {"kind": "token", "token": content}
