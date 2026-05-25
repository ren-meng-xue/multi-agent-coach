"""LangGraph definition for the single interviewer agent."""
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
    """Convert SQLAlchemy asyncpg URLs to psycopg-compatible Postgres URLs."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def route_after_load(state: InterviewState) -> str:
    """Choose the next phase based on persisted run state."""
    if state.get("prepared_questions"):
        return "ask_question"

    if state.get("stage") == "closing":
        return "closing"
    if state.get("stage") == "briefing":
        return "briefing"
    if state.get("stage") == "opening":
        return "briefing" if state.get("opening_complete") else "opening"
    if state.get("question_count", 0) <= 0:
        return "ask_question"
    return "decide_next"


def route_after_briefing(state: InterviewState) -> str:
    """Route after briefing stage based on user intent."""
    intent = state.get("briefing_intent")
    if intent == "continue":
        return "ask_question"
    if intent == "change_info":
        return "opening"
    return "end"



def route_after_decide(state: InterviewState) -> str:
    """Route after LLM decision.

    Hard guards take precedence: only close when question quota is met.
    LLM's closing decision is honored only if questions are exhausted.
    """
    action = state.get("decision_action")
    question_count = state.get("question_count", 0)
    total_questions = state.get("total_questions", 6)
    followup_count = state.get("followup_count", 0)
    max_followups = state.get("max_followups", 5)

    questions_exhausted = question_count >= total_questions
    followups_exhausted = followup_count >= max_followups

    # 题目未完成时，忽略 LLM 的 closing 决定，强制继续出题
    if action == "closing" and not questions_exhausted:
        return "ask_question"

    # 达到硬性上限时无条件关闭
    if questions_exhausted and followups_exhausted:
        return "closing"

    if action == "closing":
        return "closing"

    if action == "followup" and not followups_exhausted:
        return "followup"

    # 最后一题追问完毕或 LLM 选择 next_question
    if questions_exhausted:
        return "closing"

    return "ask_question"


def build_interviewer_graph(checkpointer: Any | None = None):
    """Build and compile the interviewer StateGraph."""
    graph = StateGraph(InterviewState)
    graph.add_node("load_context", nodes.load_context_node)
    graph.add_node("opening", nodes.opening_node)
    graph.add_node("briefing", nodes.briefing_node)
    graph.add_node("ask_question", nodes.ask_question_node)
    graph.add_node("decide_next", nodes.decide_next_node)
    graph.add_node("followup", nodes.followup_node)
    graph.add_node("closing", nodes.closing_node)
    graph.add_node("report", nodes.report_node)

    graph.set_entry_point("load_context")
    graph.add_conditional_edges(
        "load_context",
        route_after_load,
        {
            "opening": "opening",
            "briefing": "briefing",
            "ask_question": "ask_question",
            "decide_next": "decide_next",
            "closing": "closing",
        },
    )
    graph.add_conditional_edges(
        "decide_next",
        route_after_decide,
        {
            "followup": "followup",
            "ask_question": "ask_question",
            "closing": "closing",
        },
    )
    graph.add_conditional_edges(
        "briefing",
        route_after_briefing,
        {
            "ask_question": "ask_question",
            "opening": "opening",
            "end": END,
        },
    )
    graph.add_edge("opening", END)
    graph.add_edge("ask_question", END)
    graph.add_edge("followup", END)
    graph.add_edge("closing", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)



def get_interviewer_graph():
    """Return the currently configured interviewer graph."""
    global _interviewer_graph
    if _interviewer_graph is None:
        _interviewer_graph = build_interviewer_graph()
    return _interviewer_graph


async def setup_interviewer_checkpointer(database_url: str) -> None:
    """Initialize Postgres checkpointing for the interviewer graph."""
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
    """Close the Postgres checkpointer connection and reset to non-persistent graph."""
    global _checkpoint_stack, _interviewer_graph
    if _checkpoint_stack is not None:
        await _checkpoint_stack.aclose()
        _checkpoint_stack = None
    _interviewer_graph = build_interviewer_graph()


async def run_interviewer_turn(state: InterviewState) -> InterviewState:
    """Run one user turn through the interviewer graph."""
    thread_id = state["session_id"]
    return await get_interviewer_graph().ainvoke(
        state,
        config={"configurable": {"thread_id": thread_id}},
    )


def _stream_chunk_text(chunk: Any) -> str:
    """Extract token text from LangChain chat model stream chunks."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


async def stream_interviewer_turn_events(state: InterviewState) -> AsyncIterator[dict[str, Any]]:
    """Stream answer tokens from LangGraph and yield the final graph state.

    Only chat model calls tagged by answer-generation nodes are exposed as user-visible tokens,
    so structured routing/extraction calls never leak into the SSE response.
    """
    thread_id = state["session_id"]
    final_state: InterviewState | None = None
    async for event in get_interviewer_graph().astream_events(
        state,
        config={"configurable": {"thread_id": thread_id}},
        version="v2",
    ):
        if event.get("event") == "on_chat_model_stream" and "interviewer_answer_stream" in event.get(
            "tags", []
        ):
            text = _stream_chunk_text(event.get("data", {}).get("chunk"))
            if text:
                yield {"event": "token", "data": {"text": text}}
            continue

        if event.get("event") == "on_chain_end" and event.get("name") == "LangGraph":
            final_state = event.get("data", {}).get("output")

    if final_state is None:
        raise RuntimeError("interviewer graph did not produce final state")
    yield {"event": "final", "data": final_state}
