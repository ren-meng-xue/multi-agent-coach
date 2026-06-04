# backend/tests/unit/test_prepare_graph.py
import asyncio

import pytest

from app.agents.prepare.state import PrepareState


@pytest.mark.asyncio
async def test_supervisor_router_routes_to_next_action():
    from app.agents.prepare.graph import _supervisor_router

    state: PrepareState = {
        "next_action": "memory_search",
    }
    assert _supervisor_router(state) == "memory_search"


@pytest.mark.asyncio
async def test_supervisor_router_fans_out_memory_and_research_when_both_ready():
    from app.agents.prepare.graph import _supervisor_router

    state: PrepareState = {
        "next_action": "memory_search",
        "user_direction": "AI Agent 工程师",
        "jd_raw": "JD...",
        "completed_tools": [],
    }

    assert _supervisor_router(state) == ["memory_search", "research_agent"]


@pytest.mark.asyncio
async def test_supervisor_router_need_direction_returns_wait():
    from app.agents.prepare.graph import _supervisor_router

    state: PrepareState = {
        "next_action": "need_direction",
    }
    assert _supervisor_router(state) == "wait_direction"


@pytest.mark.asyncio
async def test_supervisor_router_end_returns_end():
    from app.agents.prepare.graph import _supervisor_router

    state: PrepareState = {
        "next_action": "END",
    }
    assert _supervisor_router(state) == "END"


def test_memory_search_completion_trace_is_backend_generated():
    from app.agents.prepare.graph import _node_completion_trace

    lines = _node_completion_trace(
        "memory_search",
        {
            "weak_areas": ["技术深度不足"],
        },
    )

    assert "读取到历史薄弱点 1 项。" in lines
    assert any("技术深度不足" in line for line in lines)


def test_jd_analysis_completion_trace_handles_missing_jd():
    from app.agents.prepare.graph import _node_completion_trace

    assert _node_completion_trace("jd_analysis", {"jd_context": None}) == [
        "未提供具体的职位描述（JD）。"
    ]


@pytest.mark.asyncio
async def test_prepare_graph_fans_out_and_merges_parallel_state(monkeypatch):
    """同时有用户方向和 JD 时，memory_search 与 research_agent 同轮启动并合并 state。"""
    from app.agents.prepare import graph as graph_module

    memory_started = asyncio.Event()
    research_started = asyncio.Event()
    starts: list[str] = []

    async def fake_supervisor(state: PrepareState) -> PrepareState:
        completed = state.get("completed_tools", [])
        if "question_gen" in completed:
            return {**state, "next_action": "END", "iteration_count": state.get("iteration_count", 0) + 1}
        if "memory_search" in completed and "research_agent" in completed:
            return {**state, "next_action": "question_gen", "direction": "AI Agent 工程师"}
        return {**state, "next_action": "memory_search", "direction": "AI Agent 工程师"}

    async def fake_memory_search(state: PrepareState) -> PrepareState:
        starts.append("memory_search")
        memory_started.set()
        await asyncio.wait_for(research_started.wait(), timeout=1)
        return {
            **state,
            "user_background": "简历摘要",
            "weak_areas": ["技术深度不足"],
            "completed_tools": state.get("completed_tools", []) + ["memory_search"],
        }

    async def fake_research_agent(state: PrepareState) -> PrepareState:
        starts.append("research_agent")
        research_started.set()
        await asyncio.wait_for(memory_started.wait(), timeout=1)
        return {
            "job_intel": {"resume_match": {"gaps": ["缺分布式"]}},
            "completed_tools": ["research_agent"],
        }

    async def fake_question_gen(state: PrepareState) -> PrepareState:
        return {
            **state,
            "prepared_questions": [],
            "summary": "done",
            "completed_tools": state.get("completed_tools", []) + ["question_gen"],
        }

    monkeypatch.setattr(graph_module.nodes, "supervisor_node", fake_supervisor)
    monkeypatch.setattr(graph_module.nodes, "memory_search_node", fake_memory_search)
    monkeypatch.setattr(graph_module.nodes, "question_gen_node", fake_question_gen)
    monkeypatch.setattr(graph_module, "_research_agent_lazy", fake_research_agent)

    graph = graph_module._build_graph()
    final = await asyncio.wait_for(
        graph.ainvoke(
            {
                "session_id": "s1",
                "user_id": "u1",
                "user_direction": "AI Agent 工程师",
                "jd_raw": "JD...",
                "completed_tools": [],
            }
        ),
        timeout=1,
    )

    assert set(starts) == {"memory_search", "research_agent"}
    assert final["weak_areas"] == ["技术深度不足"]
    assert final["user_background"] == "简历摘要"
    assert final["job_intel"]["resume_match"]["gaps"] == ["缺分布式"]
    assert final["completed_tools"] == ["memory_search", "research_agent", "question_gen"]


@pytest.mark.asyncio
async def test_prepare_graph_runs_jd_analysis_after_research_fallback(monkeypatch):
    """research_agent 返回 job_intel=None 后，Supervisor 继续进入 jd_analysis 兜底。"""
    from app.agents.prepare import graph as graph_module

    visited: list[str] = []

    async def fake_supervisor(state: PrepareState) -> PrepareState:
        completed = state.get("completed_tools", [])
        if "question_gen" in completed:
            return {**state, "next_action": "END"}
        if "research_agent" in completed and state.get("job_intel") is None and "jd_analysis" not in completed:
            return {**state, "next_action": "jd_analysis", "direction": "AI Agent 工程师"}
        if "jd_analysis" in completed:
            return {**state, "next_action": "question_gen", "direction": "AI Agent 工程师"}
        return {**state, "next_action": "memory_search", "direction": "AI Agent 工程师"}

    async def fake_memory_search(state: PrepareState) -> PrepareState:
        visited.append("memory_search")
        return {
            **state,
            "weak_areas": ["表达结构不清晰"],
            "completed_tools": state.get("completed_tools", []) + ["memory_search"],
        }

    async def fake_research_agent(state: PrepareState) -> PrepareState:
        visited.append("research_agent")
        return {"job_intel": None, "completed_tools": ["research_agent"]}

    async def fake_jd_analysis(state: PrepareState) -> PrepareState:
        visited.append("jd_analysis")
        return {
            **state,
            "jd_context": {
                "company": "Acme",
                "role": "AI Agent 工程师",
                "key_skills": ["LangGraph"],
                "focus_areas": ["Agent 编排"],
                "difficulty": "medium",
            },
            "completed_tools": state.get("completed_tools", []) + ["jd_analysis"],
        }

    async def fake_question_gen(state: PrepareState) -> PrepareState:
        visited.append("question_gen")
        return {
            **state,
            "prepared_questions": [],
            "summary": "done",
            "completed_tools": state.get("completed_tools", []) + ["question_gen"],
        }

    monkeypatch.setattr(graph_module.nodes, "supervisor_node", fake_supervisor)
    monkeypatch.setattr(graph_module.nodes, "memory_search_node", fake_memory_search)
    monkeypatch.setattr(graph_module.nodes, "jd_analysis_node", fake_jd_analysis)
    monkeypatch.setattr(graph_module.nodes, "question_gen_node", fake_question_gen)
    monkeypatch.setattr(graph_module, "_research_agent_lazy", fake_research_agent)

    graph = graph_module._build_graph()
    final = await graph.ainvoke(
        {
            "session_id": "s1",
            "user_id": "u1",
            "user_direction": "AI Agent 工程师",
            "jd_raw": "JD...",
            "completed_tools": [],
        }
    )

    assert "research_agent" in visited
    assert "jd_analysis" in visited
    assert visited.index("research_agent") < visited.index("jd_analysis")
    assert final["job_intel"] is None
    assert final["jd_context"]["role"] == "AI Agent 工程师"


@pytest.mark.asyncio
async def test_memory_search_delta_always_includes_weak_areas_when_unchanged(monkeypatch):
    """resume 路径：before state 已有 weak_areas，memory_search_node 返回相同值，
    _memory_search_delta 仍须强制把 weak_areas 写入 delta，
    使 stream_prepare_events 的 node_done SSE 里 weak_areas 不为空。"""
    from app.agents.prepare import graph as graph_module

    SAME_WEAK_AREAS = ["系统设计", "并发编程"]

    # memory_search_node 返回与 before state 完全相同的 weak_areas
    async def fake_memory_search(state: PrepareState) -> PrepareState:
        return {
            **state,
            "weak_areas": SAME_WEAK_AREAS,
            "completed_tools": state.get("completed_tools", []) + ["memory_search"],
        }

    async def fake_supervisor(state: PrepareState) -> PrepareState:
        completed = state.get("completed_tools", [])
        if "question_gen" in completed:
            return {**state, "next_action": "END"}
        if "memory_search" in completed:
            return {**state, "next_action": "question_gen"}
        return {**state, "next_action": "memory_search"}

    async def fake_question_gen(state: PrepareState) -> PrepareState:
        return {
            **state,
            "prepared_questions": [],
            "summary": "done",
            "completed_tools": state.get("completed_tools", []) + ["question_gen"],
        }

    monkeypatch.setattr(graph_module.nodes, "memory_search_node", fake_memory_search)
    monkeypatch.setattr(graph_module.nodes, "supervisor_node", fake_supervisor)
    monkeypatch.setattr(graph_module.nodes, "question_gen_node", fake_question_gen)

    # 重新编译 graph，使 monkeypatch 生效
    graph = graph_module._build_graph()
    monkeypatch.setattr(graph_module, "_prepare_graph", graph)

    # before state 里已有 weak_areas（模拟从 Redis 恢复的 resume 路径）
    init_state: PrepareState = {
        "session_id": "s-resume",
        "user_id": "u1",
        "weak_areas": SAME_WEAK_AREAS,  # 与 memory_search_node 返回值相同
        "completed_tools": [],
    }

    node_done_events: list[dict] = []
    async for sse in graph_module.stream_prepare_events(init_state):
        if sse.get("event") == "node_done" and sse.get("data", {}).get("node") == "memory_search":
            node_done_events.append(sse)

    assert node_done_events, "应当收到至少一个 memory_search node_done 事件"
    payload = node_done_events[0]["data"]
    assert "weak_areas" in payload, "node_done 必须包含 weak_areas 字段"
    assert payload["weak_areas"] == SAME_WEAK_AREAS, (
        f"weak_areas 应为 {SAME_WEAK_AREAS}，实际为 {payload['weak_areas']}"
    )
