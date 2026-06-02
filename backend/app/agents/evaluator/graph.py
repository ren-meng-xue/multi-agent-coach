"""LangGraph definition for the Evaluator Agent."""
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.evaluator import nodes
from app.agents.evaluator.state import EvaluatorState


def build_evaluator_graph():
    graph = StateGraph(EvaluatorState)
    graph.add_node("analyze_answer", nodes.analyze_answer)
    graph.add_node("update_profile", nodes.update_profile)
    graph.add_node("respond_to_chief", nodes.respond_to_chief)
    graph.set_entry_point("analyze_answer")
    graph.add_edge("analyze_answer", "update_profile")
    graph.add_edge("update_profile", "respond_to_chief")
    graph.add_edge("respond_to_chief", END)
    return graph.compile()


async def run_evaluator(state: EvaluatorState) -> dict[str, Any]:
    out = await build_evaluator_graph().ainvoke(state)
    return dict(out.get("report") or {})
