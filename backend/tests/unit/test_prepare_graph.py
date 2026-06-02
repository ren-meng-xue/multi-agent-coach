# backend/tests/unit/test_prepare_graph.py
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
