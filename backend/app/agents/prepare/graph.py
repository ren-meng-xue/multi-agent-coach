# backend/app/agents/prepare/graph.py
"""LangGraph definition and SSE streaming for the prepare pipeline."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.prepare import nodes
from app.agents.prepare.state import PrepareState
from app.core.logging import get_logger

log = get_logger("app.agents.prepare.graph")

_NODE_MAP = {
    "memory_search": nodes.memory_search_node,
    "jd_analysis": nodes.jd_analysis_node,
    "question_gen": nodes.question_gen_node,
}

_NODE_LABELS = {
    "master": "MASTER",
    "memory_search": "记忆检索",
    "jd_analysis": "JD分析",
    "question_gen": "出题",
}


def route_after_master(state: PrepareState) -> str:
    if state.get("need_direction"):
        return "wait_direction"
    chain = state.get("chain") or []
    if chain:
        return chain[0]
    return "question_gen"


def _route_next_in_chain(current: str):
    """返回 chain 里 current 之后的下一个节点名。"""
    def _route(state: PrepareState) -> str:
        chain = state.get("chain") or []
        try:
            idx = chain.index(current)
            if idx + 1 < len(chain):
                return chain[idx + 1]
        except ValueError:
            pass
        return END
    return _route


def _build_graph() -> Any:
    g = StateGraph(PrepareState)
    g.add_node("master", nodes.master_node)
    g.add_node("memory_search", nodes.memory_search_node)
    g.add_node("jd_analysis", nodes.jd_analysis_node)
    g.add_node("question_gen", nodes.question_gen_node)

    g.set_entry_point("master")
    g.add_conditional_edges(
        "master",
        route_after_master,
        {
            "memory_search": "memory_search",
            "jd_analysis": "jd_analysis",
            "question_gen": "question_gen",
            "wait_direction": END,  # 暂停等用户输入，resume 时重新触发
        },
    )

    # 动态路由：每个子 Agent 完成后看 chain 里下一个是谁
    for node_name in ("memory_search", "jd_analysis"):
        g.add_conditional_edges(
            node_name,
            _route_next_in_chain(node_name),
            {
                "jd_analysis": "jd_analysis",
                "question_gen": "question_gen",
                END: END,
            },
        )
    g.add_edge("question_gen", END)
    return g.compile()


_prepare_graph = _build_graph()


def get_prepare_graph() -> Any:
    return _prepare_graph


def _extract_token(event: dict[str, Any]) -> str | None:
    """从 astream_events 事件提取 token 文本。"""
    if event.get("event") != "on_chat_model_stream":
        return None
    content = event.get("data", {}).get("chunk", {})
    text = getattr(content, "content", "")
    return text if isinstance(text, str) else None


async def stream_prepare_events(state: PrepareState) -> AsyncIterator[dict[str, Any]]:
    """运行 prepare graph，流式 yield SSE 事件。"""
    # 率先吐出 session_id 给前端，用于断点继续时的凭证
    if state.get("session_id"):
        yield {
            "event": "init",
            "data": {
                "session_id": state.get("session_id")
            }
        }

    current_node: str | None = None
    elapsed_tracker: dict[str, float] = {}
    finished_nodes: set[str] = set()

    async for event in get_prepare_graph().astream_events(state, version="v2"):
        ev_name = event.get("event", "")
        ev_node = event.get("metadata", {}).get("langgraph_node", "")

        # 节点开始
        if ev_name == "on_chain_start" and ev_node and ev_node != current_node:
            current_node = ev_node
            elapsed_tracker[ev_node] = time.time()
            yield {
                "event": "node_start",
                "data": {
                    "node": ev_node,
                    "label": _NODE_LABELS.get(ev_node, ev_node),
                },
            }

        # 流式 token（master + question_gen）
        token = _extract_token(event)
        tags = event.get("tags", [])
        if token and any(t in tags for t in ("prepare_master_stream", "prepare_question_gen_stream")):
            yield {"event": "node_token", "data": {"node": ev_node, "text": token}}

        # 节点结束
        if ev_name == "on_chain_end" and ev_node and ev_node not in finished_nodes:
            # 只有当 event['name'] 跟 ev_node 一致或者是顶级节点时才算真正结束
            # astream_events 会 yield 子 chain 的结束
            if event.get("name") != ev_node:
                continue

            finished_nodes.add(ev_node)
            elapsed_ms = int((time.time() - elapsed_tracker.get(ev_node, time.time())) * 1000)
            node_state = event.get("data", {}).get("output") or {}

            extra: dict[str, Any] = {"elapsed_ms": elapsed_ms}
            if ev_node == "master":
                # 兼容 Pydantic 对象和 dict
                node_dict = node_state
                if hasattr(node_state, "model_dump"):
                    node_dict = node_state.model_dump()
                elif hasattr(node_state, "dict"):
                    node_dict = node_state.dict()
                
                if isinstance(node_dict, dict):
                    extra["chain"] = node_dict.get("chain", [])
                    extra["need_direction"] = node_dict.get("need_direction", False)

            yield {"event": "node_done", "data": {"node": ev_node, **extra}}

        # 全图结束
        if ev_name == "on_chain_end" and event.get("name") == "LangGraph":
            from typing import cast
            final = cast(PrepareState, event.get("data", {}).get("output") or {})
            
            # 将最新的 weak_areas 和 star_stories 写入 Redis 缓存，防止二次重定向时状态丢失
            session_id = final.get("session_id")
            user_id = final.get("user_id")
            if session_id and user_id:
                try:
                    import json

                    from app.services.coach_opening import get_coach_redis
                    r = await get_coach_redis()
                    cache_data = {
                        "weak_areas": final.get("weak_areas", []),
                        "star_stories": final.get("star_stories", []),
                    }
                    await r.setex(
                        f"prepare:state:{user_id}:{session_id}",
                        3600,  # 缓存1小时
                        json.dumps(cache_data, ensure_ascii=False),
                    )
                    log.info("prepare_state_cached", session_id=session_id)
                except Exception as exc:
                    log.warning("prepare_state_cache_failed", session_id=session_id, error=str(exc))

            if not final.get("need_direction"):
                yield {
                    "event": "done",
                    "data": {
                        "jd_context": final.get("jd_context"),
                        "prepared_questions": final.get("prepared_questions", []),
                        "summary": final.get("summary", ""),
                        "direction": final.get("direction", ""),
                    },
                }
