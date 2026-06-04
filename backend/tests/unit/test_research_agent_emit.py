"""research_agent 工具级 emit / 摘要辅助函数测试。"""
from __future__ import annotations

import pytest


def test_summarize_args_truncates_long_strings():
    from app.agents.prepare.research_agent import _summarize_args
    result = _summarize_args({"text": "x" * 100, "max_results": 5})
    assert "text=" in result
    assert "..." in result
    assert "max_results=5" in result


def test_summarize_args_describes_lists_and_dicts():
    from app.agents.prepare.research_agent import _summarize_args
    result = _summarize_args({"items": [1, 2, 3], "extra": {"a": 1, "b": 2}})
    assert "items=<list len=3>" in result
    assert "extra=<dict len=2>" in result


def test_summarize_result_for_dict_lists_keys():
    from app.agents.prepare.research_agent import _summarize_result
    result = _summarize_result({"title": "x", "company": "y", "requirements": []})
    assert "title" in result and "company" in result and "requirements" in result
    assert result.startswith("{") and result.endswith("}")


def test_summarize_result_for_list_shows_count():
    from app.agents.prepare.research_agent import _summarize_result
    result = _summarize_result([{"a": 1}, {"a": 2}, {"a": 3}])
    assert result == "[3 条结果]"


def test_summarize_result_truncates_long_string():
    from app.agents.prepare.research_agent import _summarize_result
    result = _summarize_result("x" * 200)
    assert result.endswith("...")
    assert len(result) <= 130


import json
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage


def _mock_tool(name: str, return_value):
    t = MagicMock()
    t.name = name
    t.ainvoke = AsyncMock(return_value=return_value)
    return t


@pytest.mark.asyncio
async def test_research_agent_emits_full_react_step_sequence():
    """ReAct loop 应按 think_start → think_token* → think_done → tool_call_start → tool_call_done 顺序 emit。"""
    from app.agents.prepare.research_agent import research_agent_node

    fake_report = {
        "job_interpretation": {}, "resume_match": {},
        "company_profile": {}, "interview_qa": [],
        "salary_range": {}, "prep_suggestions": [],
    }
    tools = [_mock_tool("generate_position_report", fake_report)]

    from langchain_core.messages import AIMessageChunk
    
    # 第 1 轮：LLM streaming 吐两个 chunk 然后调 generate_position_report
    chunk1 = AIMessageChunk(content="我先调研")
    chunk2 = AIMessageChunk(
        content="目标岗位",
        tool_call_chunks=[{"name": "generate_position_report", "args": '{"title": "后端", "company": "字节", "jd_summary": "...", "requirements": [], "search_results": {}, "directions": ["x"]}', "id": "c1", "index": 0}]
    )
    msg = AIMessage(
        content="我先调研目标岗位",
        tool_calls=[{
            "name": "generate_position_report",
            "args": {"title": "后端", "company": "字节", "jd_summary": "...",
                     "requirements": [], "search_results": {}, "directions": ["x"]},
            "id": "c1",
        }],
    )
    stop_msg = AIMessage(content="完成")

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)

    async def astream_side(messages):
        for c in [chunk1, chunk2]:
            yield c

    mock_model.astream = astream_side
    mock_model.ainvoke = AsyncMock(side_effect=[msg, stop_msg])

    emitted: list[dict] = []

    def fake_writer(payload):
        emitted.append(payload)

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=tools),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
        patch("app.agents.prepare.research_agent.get_stream_writer", return_value=fake_writer),
    ):
        await research_agent_node(state)

    kinds = [e.get("kind") for e in emitted]
    # 至少应包含完整一轮的事件序列
    assert "tool_thinking_start" in kinds
    assert "tool_thinking_token" in kinds
    assert "tool_thinking_done" in kinds
    assert "tool_call_start" in kinds
    assert "tool_call_done" in kinds

    # tool_call_start 的 tool_name + args_summary 字段存在
    tc_start = next(e for e in emitted if e.get("kind") == "tool_call_start")
    assert tc_start["tool_name"] == "generate_position_report"
    assert "title=" in tc_start["tool_args_summary"]

    # tool_call_done 的 result_summary + elapsed_ms 存在
    tc_done = next(e for e in emitted if e.get("kind") == "tool_call_done")
    assert "job_interpretation" in tc_done["tool_result_summary"]
    assert tc_done["tool_elapsed_ms"] >= 0

    # iteration 字段都在
    for e in emitted:
        assert "iteration" in e


@pytest.mark.asyncio
async def test_research_agent_emits_tool_error_on_failure():
    """工具调用抛错时 tool_call_done 应带 tool_error 字段。"""
    from app.agents.prepare.research_agent import research_agent_node

    failing = MagicMock()
    failing.name = "extract_jd_text"
    failing.ainvoke = AsyncMock(side_effect=RuntimeError("upstream 500"))
    # generate_position_report 也提供，便于兜底
    fake_report = {"job_interpretation": {}, "resume_match": {}, "company_profile": {}, "interview_qa": [], "salary_range": {}, "prep_suggestions": []}
    report_tool = MagicMock(); report_tool.name = "generate_position_report"; report_tool.ainvoke = AsyncMock(return_value=fake_report)

    msg = AIMessage(content="", tool_calls=[{
        "name": "extract_jd_text",
        "args": {"text": "..."},
        "id": "c1",
    }])
    stop_msg = AIMessage(content="")

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)

    async def empty_stream(messages):
        return
        yield  # never

    mock_model.astream = empty_stream
    mock_model.ainvoke = AsyncMock(side_effect=[msg, stop_msg])

    emitted: list[dict] = []

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[failing, report_tool]),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
        patch("app.agents.prepare.research_agent.get_stream_writer", return_value=emitted.append),
    ):
        await research_agent_node(state)

    tc_done = next((e for e in emitted if e.get("kind") == "tool_call_done"), None)
    assert tc_done is not None
    assert tc_done.get("tool_error", "").startswith("upstream 500")


@pytest.mark.asyncio
async def test_research_agent_writer_none_does_not_raise():
    """get_stream_writer 返回 None（兼容场景）时节点不应崩。"""
    from app.agents.prepare.research_agent import research_agent_node

    fake_report = {"job_interpretation": {}, "resume_match": {}, "company_profile": {}, "interview_qa": [], "salary_range": {}, "prep_suggestions": []}
    report_tool = MagicMock(); report_tool.name = "generate_position_report"; report_tool.ainvoke = AsyncMock(return_value=fake_report)

    msg = AIMessage(content="", tool_calls=[{
        "name": "generate_position_report",
        "args": {"title": "x", "company": "y", "jd_summary": "", "requirements": [], "search_results": {}, "directions": ["x"]},
        "id": "c1",
    }])
    stop_msg = AIMessage(content="")

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)

    async def empty_stream(messages):
        return
        yield

    mock_model.astream = empty_stream
    mock_model.ainvoke = AsyncMock(side_effect=[msg, stop_msg])

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[report_tool]),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
        patch("app.agents.prepare.research_agent.get_stream_writer", return_value=None),
    ):
        result = await research_agent_node(state)

    assert result["job_intel"] is not None
