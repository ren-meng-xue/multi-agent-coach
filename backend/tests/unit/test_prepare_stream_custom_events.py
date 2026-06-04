"""验证 stream_prepare_events 能把 on_custom 事件转换为前端约定的 SSE event。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_stream_forwards_tool_thinking_token_as_sse_event():
    """on_custom + kind=tool_thinking_token 应被转换为 event=tool_thinking_token 的 SSE 输出。"""
    from app.agents.prepare.graph import stream_prepare_events

    async def fake_astream_events(state, version="v2"):
        # 模拟 LangGraph 抛出 on_custom 事件
        yield {
            "event": "on_custom",
            "metadata": {"langgraph_node": "research_agent"},
            "data": {
                "kind": "tool_thinking_token",
                "iteration": 0,
                "step_id": "think-0",
                "text": "我先调研",
            },
        }
        # 然后图结束
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {"output": {"need_direction": False, "prepared_questions": [], "jd_context": None, "summary": "", "direction": "x"}},
        }

    mock_graph = MagicMock()
    mock_graph.astream_events = fake_astream_events

    events = []
    with patch("app.agents.prepare.graph.get_prepare_graph", return_value=mock_graph):
        async for ev in stream_prepare_events({"session_id": "s1"}):
            events.append(ev)

    matched = [e for e in events if e.get("event") == "tool_thinking_token"]
    assert len(matched) == 1
    assert matched[0]["data"]["text"] == "我先调研"
    assert matched[0]["data"]["iteration"] == 0
    assert matched[0]["data"]["node"] == "research_agent"


@pytest.mark.asyncio
async def test_stream_forwards_all_five_tool_event_kinds():
    """5 类工具级事件都能正确透传 SSE event 名。"""
    from app.agents.prepare.graph import stream_prepare_events

    kinds = [
        "tool_thinking_start", "tool_thinking_token", "tool_thinking_done",
        "tool_call_start", "tool_call_done",
    ]

    async def fake_astream_events(state, version="v2"):
        for k in kinds:
            yield {
                "event": "on_custom",
                "metadata": {"langgraph_node": "research_agent"},
                "data": {"kind": k, "iteration": 0, "step_id": "x"},
            }
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {"output": {"need_direction": False, "prepared_questions": [], "jd_context": None, "summary": "", "direction": ""}},
        }

    mock_graph = MagicMock()
    mock_graph.astream_events = fake_astream_events

    seen = set()
    with patch("app.agents.prepare.graph.get_prepare_graph", return_value=mock_graph):
        async for ev in stream_prepare_events({"session_id": "s1"}):
            if ev["event"] in kinds:
                seen.add(ev["event"])

    assert seen == set(kinds)