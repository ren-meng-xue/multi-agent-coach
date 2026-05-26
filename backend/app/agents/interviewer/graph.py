"""LangGraph definition for the multi-agent interviewer."""
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from app.agents.interviewer import nodes
from app.agents.interviewer.state import InterviewState

_interviewer_graph: Any | None = None
_checkpoint_stack: AsyncExitStack | None = None


def _to_psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


CHAIN_NODES = {"evaluator", "followup", "ask_question", "closing"}


def route_after_master(state: InterviewState) -> str:
    chain = state.get("chain") or []
    if not chain:
        return "followup"  # 防御性 fallback
    head = chain[0]
    if head not in CHAIN_NODES:
        return "followup"
    return head


def _route_next_in_chain(current: str):
    def _route(state: InterviewState) -> str:
        chain = state.get("chain") or []
        try:
            idx = chain.index(current)
        except ValueError:
            return END
        if idx + 1 >= len(chain):
            return END
        return chain[idx + 1]
    return _route


def build_interviewer_graph(checkpointer: Any | None = None):
    graph = StateGraph(InterviewState)
    graph.add_node("load_context", nodes.load_context_node)
    graph.add_node("master", nodes.master_node)
    graph.add_node("evaluator", nodes.evaluator_node)
    graph.add_node("ask_question", nodes.ask_question_node)
    graph.add_node("followup", nodes.followup_node)
    graph.add_node("closing", nodes.closing_node)
    graph.add_node("report", nodes.report_node)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "master")

    graph.add_conditional_edges(
        "master",
        route_after_master,
        {
            "evaluator": "evaluator",
            "followup": "followup",
            "ask_question": "ask_question",
            "closing": "closing",
        },
    )

    # evaluator 后看 chain 下一个
    graph.add_conditional_edges(
        "evaluator",
        _route_next_in_chain("evaluator"),
        {
            "followup": "followup",
            "ask_question": "ask_question",
            "closing": "closing",
            END: END,
        },
    )

    graph.add_edge("ask_question", END)
    graph.add_edge("followup", END)
    graph.add_edge("closing", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)


def get_interviewer_graph():
    global _interviewer_graph
    if _interviewer_graph is None:
        _interviewer_graph = build_interviewer_graph()
    return _interviewer_graph


async def setup_interviewer_checkpointer(database_url: str) -> None:
    global _checkpoint_stack, _interviewer_graph
    if _checkpoint_stack is not None:
        await _checkpoint_stack.aclose()

    stack = AsyncExitStack()
    checkpointer = await stack.enter_async_context(
        AsyncPostgresSaver.from_conn_string(_to_psycopg_url(database_url))
    )
    await checkpointer.setup()
    _checkpoint_stack = stack
    _interviewer_graph = build_interviewer_graph(checkpointer=checkpointer)


async def close_interviewer_checkpointer() -> None:
    global _checkpoint_stack, _interviewer_graph
    if _checkpoint_stack is not None:
        await _checkpoint_stack.aclose()
        _checkpoint_stack = None
    _interviewer_graph = build_interviewer_graph()


async def run_interviewer_turn(state: InterviewState) -> InterviewState:
    thread_id = state["session_id"]
    return await get_interviewer_graph().ainvoke(
        state,
        config={"configurable": {"thread_id": thread_id}},
    )


# stream_interviewer_turn_events 在 Task 13 重写
async def stream_interviewer_turn_events(state: InterviewState) -> AsyncIterator[dict[str, Any]]:
    raise NotImplementedError("stream_interviewer_turn_events rewritten in Task 13")
