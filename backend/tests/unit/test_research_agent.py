"""research_agent ReAct loop 单测（mock MCP 工具）。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


def _mock_tool(name: str, return_value):
    t = MagicMock()
    t.name = name
    t.ainvoke = AsyncMock(return_value=return_value)
    return t


@pytest.mark.asyncio
async def test_research_agent_writes_job_intel_on_success():
    """正常路径：LLM 决策调 extract_jd_text → web_search → generate_position_report，job_intel 被写入。"""
    from app.agents.prepare.research_agent import research_agent_node

    fake_report = {
        "job_interpretation": {"hard_requirements": ["Python"]},
        "resume_match": {"strengths": ["3 年经验"], "gaps": ["缺分布式"]},
        "company_profile": {"summary": "字节核心业务", "tags": ["快节奏"]},
        "interview_qa": [],
        "salary_range": {"median": 30000},
        "prep_suggestions": [{"title": "补分布式", "content": "看 DDIA"}],
    }

    mock_tools = [
        _mock_tool("extract_jd_text", {"title": "后端", "company": "字节", "requirements": ["Python"], "jd_summary": "...", "salary_range": None, "location": None, "work_type": None}),
        _mock_tool("web_search", [{"title": "blog", "url": "u", "content": "字节技术栈"}]),
        _mock_tool("generate_position_report", fake_report),
    ]

    # 第 1 轮 LLM 决策调 extract_jd_text
    msg1 = AIMessage(content="", tool_calls=[{"name": "extract_jd_text", "args": {"text": "JD..."}, "id": "c1"}])
    # 第 2 轮 LLM 决策调 web_search
    msg2 = AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "字节 后端"}, "id": "c2"}])
    # 第 3 轮 LLM 决策调 generate_position_report
    msg3 = AIMessage(content="", tool_calls=[{"name": "generate_position_report", "args": {"title": "后端", "company": "字节", "jd_summary": "...", "requirements": ["Python"], "search_results": {"general": []}, "directions": ["技术栈"]}, "id": "c3"}])
    # 第 4 轮 LLM 看到结果，不再调工具，结束
    msg4 = AIMessage(content="调研完成")

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_model.ainvoke = AsyncMock(side_effect=[msg1, msg2, msg3, msg4])

    state = {
        "user_id": "u1",
        "user_direction": "AI Agent 工程师",
        "jd_raw": "字节后端 JD...",
        "user_background": "3 年 Python",
    }

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=mock_tools),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
    ):
        result = await research_agent_node(state)

    assert result["job_intel"] is not None
    assert result["job_intel"]["resume_match"]["gaps"] == ["缺分布式"]
    assert "generate_position_report" in result["job_intel"]["_trace"]["tools_used"]
    assert "research_agent" in result.get("completed_tools", [])


@pytest.mark.asyncio
async def test_research_agent_returns_none_when_mcp_unavailable():
    """MCP 不可用（空工具列表）时，job_intel 为 None，让 Supervisor 走 jd_analysis 兜底。"""
    from app.agents.prepare.research_agent import research_agent_node

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with patch(
        "app.agents.prepare.research_agent.get_mcp_tools",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await research_agent_node(state)

    assert result["job_intel"] is None
    assert "research_agent" in result["completed_tools"]


@pytest.mark.asyncio
async def test_research_agent_stops_at_max_iterations():
    """超过 max iterations 时强制兜底调 generate_position_report 收尾。"""
    from app.agents.prepare.research_agent import research_agent_node

    fake_report = {
        "job_interpretation": {}, "resume_match": {}, "company_profile": {},
        "interview_qa": [], "salary_range": {}, "prep_suggestions": [],
    }
    report_tool = _mock_tool("generate_position_report", fake_report)
    extract_tool = _mock_tool("extract_jd_text", {"title": "x", "company": "y", "requirements": [], "jd_summary": "", "salary_range": None, "location": None, "work_type": None})

    # LLM 死循环调 extract_jd_text，每轮都不调 generate_position_report
    loop_msg = AIMessage(content="", tool_calls=[{"name": "extract_jd_text", "args": {"text": "..."}, "id": "loop"}])

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_model.ainvoke = AsyncMock(return_value=loop_msg)

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[extract_tool, report_tool]),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
    ):
        result = await research_agent_node(state)

    # 即使 LLM 死循环，节点也应该兜底调 generate_position_report 出报告
    assert result["job_intel"] is not None
    assert result["job_intel"]["_trace"]["iterations"] >= 6


@pytest.mark.asyncio
async def test_research_agent_skips_when_no_jd():
    """没 jd_raw 也没 jd_url 时直接跳过，不启动 ReAct loop。"""
    from app.agents.prepare.research_agent import research_agent_node

    state = {"user_id": "u1"}  # 没 jd_raw

    with patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock) as mock_get:
        result = await research_agent_node(state)

    mock_get.assert_not_awaited()
    assert result["job_intel"] is None
    assert "research_agent" in result["completed_tools"]


@pytest.mark.asyncio
async def test_research_agent_tool_timeout_uses_remaining_budget():
    """剩余预算低于 30 秒时，tool 调用 timeout 使用剩余总预算。"""
    from app.agents.prepare.research_agent import research_agent_node

    tool = _mock_tool("web_search", [{"title": "result"}])
    report_tool = _mock_tool("generate_position_report", None)
    msg = AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "x"}, "id": "c1"}])

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_model.ainvoke = AsyncMock(return_value=msg)

    time_values = iter([0, 70, 89, 90, 90, 90, 90])
    wait_for_timeouts: list[float] = []

    async def fake_wait_for(awaitable, timeout):
        wait_for_timeouts.append(timeout)
        return await awaitable

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[tool, report_tool]),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
        patch("app.agents.prepare.research_agent.time.time", side_effect=lambda: next(time_values)),
        patch("app.agents.prepare.research_agent.asyncio.wait_for", side_effect=fake_wait_for),
    ):
        await research_agent_node({"user_id": "u1", "jd_raw": "JD..."})

    assert wait_for_timeouts[0] == 20
    assert wait_for_timeouts[1] == 1
    assert all(timeout <= 20 for timeout in wait_for_timeouts)


@pytest.mark.asyncio
async def test_research_agent_does_not_finalize_when_budget_exhausted():
    """预算耗尽后不再额外等待 generate_position_report。"""
    from app.agents.prepare.research_agent import research_agent_node

    report_tool = _mock_tool("generate_position_report", {"job_interpretation": {}})
    msg = AIMessage(content="", tool_calls=[])

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_model.ainvoke = AsyncMock(return_value=msg)

    time_values = iter([0, 90, 90, 90, 90])

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[report_tool]),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
        patch("app.agents.prepare.research_agent.time.time", side_effect=lambda: next(time_values)),
    ):
        result = await research_agent_node({"user_id": "u1", "jd_raw": "JD..."})

    report_tool.ainvoke.assert_not_awaited()
    assert result["job_intel"] is None
    assert "research_agent" in result["completed_tools"]


@pytest.mark.asyncio
async def test_research_agent_model_exception_falls_back_without_raising():
    """LLM 非超时异常不会冒泡，节点返回 job_intel=None 并标记完成。"""
    from app.agents.prepare.research_agent import research_agent_node

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_model.ainvoke = AsyncMock(side_effect=RuntimeError("connection dropped"))

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[]),
    ):
        no_tool_result = await research_agent_node({"user_id": "u1", "jd_raw": "JD..."})

    assert no_tool_result["job_intel"] is None

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[_mock_tool("web_search", [])]),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
    ):
        result = await research_agent_node({"user_id": "u1", "jd_raw": "JD..."})

    assert result["job_intel"] is None
    assert "research_agent" in result["completed_tools"]
