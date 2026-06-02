"""LangGraph definition for the Question Designer Agent."""
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.designer import nodes
from app.agents.designer.state import DesignerState


def build_designer_graph():
    graph = StateGraph(DesignerState)
    graph.add_node("design", nodes.design)
    graph.add_node("validate", nodes.validate)
    graph.add_node("respond_to_chief", nodes.respond_to_chief)
    graph.set_entry_point("design")
    graph.add_edge("design", "validate")
    graph.add_edge("validate", "respond_to_chief")
    graph.add_edge("respond_to_chief", END)
    return graph.compile()


async def run_designer(state: DesignerState) -> dict[str, Any]:
    out = await build_designer_graph().ainvoke(state)
    return dict(out.get("output") or {})


def build_designer_dual_graph():
    graph = StateGraph(DesignerState)
    graph.add_node("design_dual", nodes.design_dual)
    graph.set_entry_point("design_dual")
    graph.add_edge("design_dual", END)
    return graph.compile()


async def run_designer_dual(state: DesignerState) -> dict[str, Any]:
    out = await build_designer_dual_graph().ainvoke(state)
    return dict(out.get("dual_output") or {})
