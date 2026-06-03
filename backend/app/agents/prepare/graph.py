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
    "supervisor": nodes.supervisor_node,
    "memory_search": nodes.memory_search_node,
    "jd_analysis": nodes.jd_analysis_node,
    "question_gen": nodes.question_gen_node,
}

_NODE_LABELS = {
    "supervisor": "调度",
    "memory_search": "记忆检索",
    "jd_analysis": "JD分析",
    "question_gen": "出题",
}

_NODE_TITLES = {
    "supervisor": "识别方向，启动准备",
    "memory_search": "读取历史表现",
    "jd_analysis": "构建岗位考点地图",
    "question_gen": "定制专属题目",
}


def _format_memory_search_trace(state: dict[str, Any]) -> list[str]:
    weak_areas = state.get("weak_areas") or []

    lines = [
        f"读取到历史薄弱点 {len(weak_areas)} 项。",
    ]
    if weak_areas:
        lines.append(f"本轮优先覆盖：{'、'.join(str(item) for item in weak_areas[:3])}。")
    else:
        lines.append("这是新用户或历史薄弱点未查询。")
    return lines


def _format_jd_analysis_trace(state: dict[str, Any]) -> list[str]:
    jd_context = state.get("jd_context")
    if not jd_context:
        return ["未提供具体的职位描述（JD）。"]

    role = jd_context.get("role") or "未识别岗位"
    company = jd_context.get("company") or "未识别公司"
    skills = jd_context.get("key_skills") or []
    focus_areas = jd_context.get("focus_areas") or []
    difficulty = jd_context.get("difficulty") or "medium"

    lines = [f"识别岗位：{role}。", f"识别公司：{company}。", f"岗位难度：{difficulty}。"]
    if skills:
        lines.append(f"关键技能：{'、'.join(str(item) for item in skills[:6])}。")
    if focus_areas:
        lines.append(f"重点考察：{'、'.join(str(item) for item in focus_areas[:6])}。")
    return lines


def _node_completion_trace(ev_node: str, state: dict[str, Any]) -> list[str]:
    if ev_node == "memory_search":
        return _format_memory_search_trace(state)
    if ev_node == "jd_analysis":
        return _format_jd_analysis_trace(state)
    return []


def _supervisor_router(state: PrepareState) -> str:
    """读取 supervisor 的决策，路由到下一节点。"""
    action = state.get("next_action", "END")
    if action == "need_direction":
        return "wait_direction"
    return action


def _build_graph() -> Any:
    g = StateGraph(PrepareState)
    g.add_node("supervisor", nodes.supervisor_node)
    g.add_node("memory_search", nodes.memory_search_node)
    g.add_node("jd_analysis", nodes.jd_analysis_node)
    g.add_node("question_gen", nodes.question_gen_node)

    g.set_entry_point("supervisor")

    # Supervisor → 各子节点（含 END）
    g.add_conditional_edges(
        "supervisor",
        _supervisor_router,
        {
            "memory_search": "memory_search",
            "jd_analysis": "jd_analysis",
            "question_gen": "question_gen",
            "wait_direction": END,
            "END": END,
        },
    )

    # 各子节点完成后回流到 supervisor
    g.add_edge("memory_search", "supervisor")
    g.add_edge("jd_analysis", "supervisor")
    g.add_edge("question_gen", "supervisor")

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
        # 对于 supervisor，允许重复触发；对于其他节点，只触发一次且避免重复 yield 同一节点
        if ev_name == "on_chain_start" and ev_node and (
            ev_node == "supervisor" or (ev_node != current_node and ev_node not in finished_nodes)
        ):
            current_node = ev_node
            elapsed_tracker[ev_node] = time.time()
            yield {
                "event": "node_start",
                "data": {
                    "node": ev_node,
                    "label": _NODE_LABELS.get(ev_node, ev_node),
                    "title": _NODE_TITLES.get(ev_node, ev_node),
                },
            }

        # 流式 token（supervisor + question_gen）
        token = _extract_token(event)
        tags = event.get("tags", [])
        if token and any(t in tags for t in ("prepare_supervisor_stream", "prepare_question_gen_stream")):
            yield {"event": "node_token", "data": {"node": ev_node, "text": token}}

        # 节点结束
        if ev_name == "on_chain_end" and ev_node:
            # 只有当 event['name'] 跟 ev_node 一致或者是顶级节点时才算真正结束
            if event.get("name") != ev_node:
                continue
            
            # 对于 supervisor 允许重复触发，其他节点只触发一次
            if ev_node != "supervisor" and ev_node in finished_nodes:
                continue

            finished_nodes.add(ev_node)
            elapsed_ms = int((time.time() - elapsed_tracker.get(ev_node, time.time())) * 1000)
            node_state = event.get("data", {}).get("output") or {}

            extra: dict[str, Any] = {"elapsed_ms": elapsed_ms}
            if ev_node == "supervisor":
                # 兼容 Pydantic 对象和 dict
                node_dict = node_state
                if hasattr(node_state, "model_dump"):
                    node_dict = node_state.model_dump()
                elif hasattr(node_state, "dict"):
                    node_dict = node_state.dict()
                
                if isinstance(node_dict, dict):
                    extra["next_action"] = node_dict.get("next_action", "END")
                    extra["need_direction"] = node_dict.get("need_direction", False)

            if isinstance(node_state, dict):
                for line in _node_completion_trace(ev_node, node_state):
                    yield {"event": "node_token", "data": {"node": ev_node, "text": f"• {line}\n"}}

            yield {"event": "node_done", "data": {"node": ev_node, **extra}}

        # 全图结束
        if ev_name == "on_chain_end" and event.get("name") == "LangGraph":
            from typing import cast
            final = cast(PrepareState, event.get("data", {}).get("output") or {})
            
            # 将最新的 weak_areas 写入 Redis 缓存，防止二次重定向时状态丢失
            session_id = final.get("session_id")
            user_id = final.get("user_id")
            if session_id and user_id:
                try:
                    import json

                    from app.services.coach_opening import get_coach_redis
                    r = await get_coach_redis()
                    cache_data = {
                        "weak_areas": final.get("weak_areas", []),
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
