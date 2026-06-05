# backend/app/agents/prepare/graph.py
"""LangGraph definition and SSE streaming for the prepare pipeline."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any, cast

from langgraph.graph import END, StateGraph

from app.agents.prepare import nodes
from app.agents.prepare.state import PrepareState
from app.core.logging import get_logger

log = get_logger("app.agents.prepare.graph")


_MISSING = object()


def _state_delta(before: PrepareState, after: PrepareState) -> PrepareState:
    """只返回节点实际改动，避免并行分支写回旧 state 覆盖彼此结果。"""
    delta: dict[str, Any] = {}
    before_dict = dict(before)
    for key, value in dict(after).items():
        if key == "completed_tools" or before_dict.get(key, _MISSING) != value:
            delta[key] = value
    return cast(PrepareState, delta)


async def _memory_search_delta(state: PrepareState) -> PrepareState:
    result = await nodes.memory_search_node(state)
    delta = dict(_state_delta(state, result))
    # Force include weak_areas: even when unchanged from before state (resume path),
    # stream_prepare_events must emit it in node_done SSE payload.
    delta["weak_areas"] = result.get("weak_areas") or []
    return cast(PrepareState, delta)


async def _research_agent_lazy(state):
    """延迟导入 research_agent，避免模块加载期触发 MCP 连接。"""
    from app.agents.prepare.research_agent import research_agent_node
    result = await research_agent_node(state)
    return _state_delta(state, result)


_NODE_MAP = {
    "supervisor": nodes.supervisor_node,
    "memory_search": nodes.memory_search_node,
    "research_agent": _research_agent_lazy,
    "jd_analysis": nodes.jd_analysis_node,
    "question_gen": nodes.question_gen_node,
}

_NODE_LABELS = {
    "supervisor": "调度",
    "memory_search": "记忆检索",
    "research_agent": "岗位调研",
    "jd_analysis": "JD分析",
    "question_gen": "出题",
}

_NODE_TITLES = {
    "supervisor": "识别方向，启动准备",
    "memory_search": "读取历史表现",
    "research_agent": "通过 MCP 调研目标岗位",
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


def _format_research_agent_trace(state: dict[str, Any]) -> list[str]:
    job_intel = state.get("job_intel")
    if not job_intel:
        return ["岗位调研未启动或失败，已回退到 JD 浅分析。"]

    trace = job_intel.get("_trace", {})
    tools = trace.get("tools_used", [])
    iters = trace.get("iterations", 0)
    elapsed = trace.get("elapsed_ms", 0)

    lines = [f"调研完成，{iters} 轮、用了 {len(tools)} 次工具调用，耗时 {elapsed} 毫秒。"]
    company = (job_intel.get("company_profile") or {}).get("summary", "")
    if company:
        lines.append(f"公司画像：{company[:120]}")
    gaps = (job_intel.get("resume_match") or {}).get("gaps", [])
    if gaps:
        lines.append(f"针对此岗位的 Gap：{', '.join(gaps[:5])}")
    return lines


def _node_completion_trace(ev_node: str, state: dict[str, Any]) -> list[str]:
    if ev_node == "memory_search":
        return _format_memory_search_trace(state)
    if ev_node == "research_agent":
        return _format_research_agent_trace(state)
    if ev_node == "jd_analysis":
        return _format_jd_analysis_trace(state)
    return []


def _has_jd(state: PrepareState) -> bool:
    return bool(state.get("jd_raw") or state.get("jd_url"))


def _supervisor_router(state: PrepareState) -> str | list[str]:
    """读取 supervisor 的决策，路由到下一节点。"""
    action = state.get("next_action", "END")
    if action == "need_direction":
        return "wait_direction"
    if action in {"memory_search", "research_agent"}:
        completed = state.get("completed_tools", [])
        should_search_memory = "memory_search" not in completed
        should_research = _has_jd(state) and "research_agent" not in completed
        targets = []
        if should_search_memory:
            targets.append("memory_search")
        if should_research:
            targets.append("research_agent")
        if len(targets) > 1:
            return targets
        if targets:
            return targets[0]
        # 两个节点都已完成但 supervisor 仍发 memory_search/research_agent，
        # 防御性推进到下一阶段，避免重复执行
        return "question_gen"
    return action


def _build_graph() -> Any:
    g = StateGraph(PrepareState)
    g.add_node("supervisor", nodes.supervisor_node)
    g.add_node("memory_search", _memory_search_delta)
    g.add_node("research_agent", _research_agent_lazy)
    g.add_node("jd_analysis", nodes.jd_analysis_node)
    g.add_node("question_gen", nodes.question_gen_node)

    g.set_entry_point("supervisor")

    # Supervisor → 各子节点（含 END）
    g.add_conditional_edges(
        "supervisor",
        _supervisor_router,
        {
            "memory_search": "memory_search",
            "research_agent": "research_agent",
            "jd_analysis": "jd_analysis",
            "question_gen": "question_gen",
            "wait_direction": END,
            "END": END,
        },
    )

    # 各子节点完成后回流到 supervisor
    g.add_edge("memory_search", "supervisor")
    g.add_edge("research_agent", "supervisor")
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

        # 工具级 SSE 事件：透传 research_agent ReAct loop 内部的自定义事件
        if ev_name == "on_custom":
            payload = event.get("data") or {}
            kind = payload.get("kind", "")
            if kind in {
                "tool_thinking_start",
                "tool_thinking_token",
                "tool_thinking_done",
                "tool_call_start",
                "tool_call_done",
            }:
                forwarded = {k: v for k, v in payload.items() if k != "kind"}
                forwarded.setdefault("node", ev_node or "research_agent")
                yield {"event": kind, "data": forwarded}
                continue

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
            _raw_output = event.get("data", {}).get("output") or {}
            # 统一转换为 plain dict，兼容 Pydantic 对象
            if hasattr(_raw_output, "model_dump"):
                node_state: dict[str, Any] = _raw_output.model_dump()
            elif hasattr(_raw_output, "dict") and not isinstance(_raw_output, dict):
                node_state = _raw_output.dict()
            else:
                node_state = _raw_output if isinstance(_raw_output, dict) else {}

            extra: dict[str, Any] = {"elapsed_ms": elapsed_ms}
            if ev_node == "supervisor":
                extra["next_action"] = node_state.get("next_action", "END")
                extra["need_direction"] = node_state.get("need_direction", False)

            if isinstance(node_state, dict):
                for line in _node_completion_trace(ev_node, node_state):
                    yield {"event": "node_token", "data": {"node": ev_node, "text": f"• {line}\n"}}

                if ev_node == "memory_search":
                    weak_areas = node_state.get("weak_areas") or []
                    extra["weak_areas"] = weak_areas
                    extra["record_count"] = len(weak_areas)
                elif ev_node == "research_agent":
                    job_intel = node_state.get("job_intel") or {}
                    trace = job_intel.get("_trace") or {}
                    extra["react_iterations"] = trace.get("iterations") or 0
                    extra["react_tool_count"] = len(trace.get("tools_used") or [])
                    
                    company_profile = job_intel.get("company_profile") or {}
                    company_name = company_profile.get("name")
                    if not company_name:
                        summary = job_intel.get("summary") or ""
                        company_name = summary[:20] if summary else ""
                    extra["company_name"] = company_name
                    
                    resume_match = job_intel.get("resume_match") or {}
                    extra["gaps"] = (resume_match.get("gaps") or [])[:3]
                elif ev_node == "jd_analysis":
                    jd_context = node_state.get("jd_context") or {}
                    extra["jd_company"] = jd_context.get("company")
                    extra["jd_role"] = jd_context.get("role")
                    extra["jd_difficulty"] = jd_context.get("difficulty")
                    extra["jd_key_skills"] = (jd_context.get("key_skills") or [])[:6]
                elif ev_node == "question_gen":
                    prepared_questions = node_state.get("prepared_questions") or []
                    stats = {}
                    for q in prepared_questions:
                        cat = q.get("category")
                        if cat:
                            stats[cat] = stats.get(cat, 0) + 1
                    
                    extra["question_stats"] = {k: v for k, v in stats.items() if v > 0}
                    extra["question_total"] = len(prepared_questions)

            yield {"event": "node_done", "data": {"node": ev_node, **extra}}

        # 全图结束
        if ev_name == "on_chain_end" and event.get("name") == "LangGraph":
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
                raw_intel = final.get("job_intel")
                intel: dict | None = (
                    {k: v for k, v in raw_intel.items() if k != "_trace"}
                    if isinstance(raw_intel, dict)
                    else None
                )
                yield {
                    "event": "done",
                    "data": {
                        "jd_context": final.get("jd_context"),
                        "job_intel": intel,
                        "prepared_questions": final.get("prepared_questions", []),
                        "summary": final.get("summary", ""),
                        "direction": final.get("direction", ""),
                    },
                }
