# backend/tests/unit/test_prepare_graph.py
import pytest

from app.agents.prepare.state import PrepareState


@pytest.mark.asyncio
async def test_route_after_master_includes_jd_when_has_jd():
    from app.agents.prepare.graph import route_after_master

    state: PrepareState = {
        "chain": ["memory_search", "jd_analysis", "question_gen"],
    }
    assert route_after_master(state) == "memory_search"


@pytest.mark.asyncio
async def test_route_after_master_skips_to_question_gen():
    from app.agents.prepare.graph import route_after_master

    state: PrepareState = {
        "chain": ["question_gen"],
    }
    assert route_after_master(state) == "question_gen"


@pytest.mark.asyncio
async def test_route_after_master_need_direction_returns_wait():
    from app.agents.prepare.graph import route_after_master

    state: PrepareState = {
        "chain": [],
        "need_direction": True,
    }
    assert route_after_master(state) == "wait_direction"


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
