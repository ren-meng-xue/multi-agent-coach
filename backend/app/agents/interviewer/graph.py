"""LangGraph definition for the multi-agent interviewer."""
import asyncio
import time as _time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from app.agents.interviewer import chief, nodes
from app.agents.interviewer.nodes import CHAIN_NODES
from app.agents.interviewer.state import InterviewState

_checkpoint_stack: AsyncExitStack | None = None
_interviewer_graph: Any = None


def _to_psycopg_url(url: str) -> str:
    """将 postgresql+asyncpg:// 转换为 postgresql:// 兼容 psycopg"""
    if "postgresql+asyncpg://" in url:
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


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
    graph.add_node("chief_think", chief.chief_think)
    graph.add_node("chief_execute", chief.chief_execute)
    graph.add_node("chief_respond", chief.chief_respond)
    graph.add_node("report", nodes.report_node)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "chief_think")

    graph.add_conditional_edges(
        "chief_think",
        chief.route_after_chief_think,
        {
            "chief_execute": "chief_execute",
            "chief_respond": "chief_respond",
        },
    )
    graph.add_edge("chief_execute", "chief_think")
    graph.add_conditional_edges(
        "chief_respond",
        chief.route_after_chief_respond,
        {
            "report": "report",
            "__end__": END,
        },
    )
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


NODE_LABELS = {
    "chief_think": "思考",
    "chief_respond": "回复",
    "master": "调度",
    "evaluator": "评估",
    "followup": "面试官 · 追问",
    "ask_question": "面试官 · 出题",
    "closing": "收尾",
}

# 不发 node_* 事件的内部节点（用户无需可见）
# designer/evaluator 子图内部节点也在此隐藏——其结果通过 chief_think node_done 向上传递
_HIDDEN_NODES = {
    "load_context", "report", "chief_execute",
    # designer 子图内部节点
    "design", "validate", "respond_to_chief",
    # evaluator 子图内部节点
    "analyze_answer", "update_profile",
    # designer_dual 子图内部节点
    "design_dual",
}


def _stream_chunk_text(chunk: Any) -> str:
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


def _latest_evaluation_payload(node_dict: dict[str, Any]) -> dict[str, Any]:
    evals = node_dict.get("turn_evaluations") or []
    if evals:
        last = evals[-1]
    else:
        report = node_dict.get("evaluator_report") or {}
        last = report.get("scoring") or {}

    if not isinstance(last, dict) or "summary_score" not in last:
        return {}

    return {
        "summary_score": last.get("summary_score"),
        "candidate_level": last.get("candidate_level"),
        "latent_signals": last.get("latent_signals", []),
        "missing_dimensions": last.get("missing_dimensions", []),
    }


async def stream_interviewer_turn_events(state: InterviewState) -> AsyncIterator[dict[str, Any]]:
    """发出 node_start / node_token / node_done / token / final 事件。"""
    thread_id = state["session_id"]
    final_state: InterviewState | None = None
    elapsed_tracker: dict[str, float] = {}
    current_node: str | None = None

    async for event in get_interviewer_graph().astream_events(
        state,
        config={"configurable": {"thread_id": thread_id}},
        version="v2",
    ):
        ev_name = event.get("event", "")
        ev_node = event.get("metadata", {}).get("langgraph_node", "")
        tags = event.get("tags", []) or []

        # 节点开始
        if (
            ev_name == "on_chain_start"
            and ev_node
            and ev_node not in _HIDDEN_NODES
            and ev_node != current_node
        ):
            current_node = ev_node
            elapsed_tracker[ev_node] = _time.time()
            yield {
                "event": "node_start",
                "data": {"node": ev_node, "label": NODE_LABELS.get(ev_node, ev_node)},
            }
            # 首轮启动静态文案流式体验模拟
            if ev_node == "chief_think" and state.get("question_count", 0) == 0:
                has_prepared_questions = bool(state.get("prepared_questions"))
                static_text = (
                    "• 从准备阶段题目池中抽取第一道题。"
                    if has_prepared_questions
                    else "• 面试正式开始，进入首题出题。"
                )
                for char in static_text:
                    yield {"event": "node_token", "data": {"node": "chief_think", "text": char}}
                    await asyncio.sleep(0.02)

        # Token 流：根据 tag 路由
        if ev_name == "on_chat_model_stream":
            text = _stream_chunk_text(event.get("data", {}).get("chunk"))
            if not text:
                continue
            if "interviewer_answer_stream" in tags:
                # 沿用现有 delta 通道供前端 onDelta 处理（不改名）
                yield {"event": "token", "data": {"text": text}}
                continue
            if "chief_think_token_stream" in tags:
                yield {"event": "node_token", "data": {"node": "chief_think", "text": text}}
                continue
            if "master_token_stream" in tags:
                yield {"event": "node_token", "data": {"node": "master", "text": text}}
                continue
            if "evaluator_token_stream" in tags:
                yield {"event": "node_token", "data": {"node": "evaluator", "text": text}}
                continue

        # 节点结束
        if ev_name == "on_chain_end" and ev_node and ev_node not in _HIDDEN_NODES:
            # 只有当 event['name'] 跟 ev_node 一致或者是顶级节点时才算真正结束
            if event.get("name") != ev_node:
                continue

            elapsed_ms = int((_time.time() - elapsed_tracker.get(ev_node, _time.time())) * 1000)
            node_state = event.get("data", {}).get("output") or {}
            payload: dict[str, Any] = {"node": ev_node, "elapsed_ms": elapsed_ms}

            # 兼容 Pydantic 对象和 dict
            node_dict = node_state
            if hasattr(node_state, "model_dump"):
                node_dict = node_state.model_dump()
            elif hasattr(node_state, "dict"):
                node_dict = node_state.dict()

            if ev_node == "master" and isinstance(node_dict, dict):
                payload["chain"] = node_dict.get("chain", [])
                payload["followup_focus"] = node_dict.get("followup_focus", "")
            if ev_node == "chief_think" and isinstance(node_dict, dict):
                msgs = node_dict.get("chief_messages") or []
                last = msgs[-1] if msgs else None
                tool_calls = [tc["name"] for tc in (getattr(last, "tool_calls", None) or [])]
                payload["chief_tool_calls"] = tool_calls
                
                # 提取思考过程：优先用流式 thoughts，没有则根据工具调用生成
                thoughts = node_dict.get("chief_thoughts", [])
                if thoughts:
                    payload["assistant_message"] = "\n".join([f"• {t}" for t in thoughts])
                elif tool_calls:
                    tool_map = {
                        "evaluate_answer": "评价候选人回答",
                        "design_question": "生成面试题目",
                        "query_profile": "查询能力画像",
                    }
                    actions = [tool_map.get(tc, tc) for tc in tool_calls]
                    payload["assistant_message"] = f"→ 决定执行以下操作：{ '、'.join(actions)}。"
                
                # 补上 designer 出题结果，供前端展示
                designer = node_dict.get("designer_output") or {}
                if designer.get("question_text"):
                    payload["designed_question"] = designer.get("question_text", "")
                    payload["designed_category"] = designer.get("question_category", "technical")
                    payload["designed_source"] = designer.get("source", "llm")
            if isinstance(node_dict, dict):
                payload.update(_latest_evaluation_payload(node_dict))
            # 对于 ask_question/followup/closing 节点，将 assistant_message 附在 node_done
            # 里，供前端在没有 LLM token 流时（如有备题路径）填充 trace 面板内容
            if ev_node in ("ask_question", "followup", "closing", "chief_respond", "chief_think") and isinstance(node_dict, dict):
                am = payload.get("assistant_message") or node_dict.get("assistant_message", "")
                if am:
                    payload["assistant_message"] = am
            yield {"event": "node_done", "data": payload}

        # 全图结束
        if ev_name == "on_chain_end" and event.get("name") == "LangGraph":
            final_state = event.get("data", {}).get("output")

    if final_state is None:
        raise RuntimeError("interviewer graph did not produce final state")
    yield {"event": "final", "data": final_state}
