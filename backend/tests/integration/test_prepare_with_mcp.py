"""Prepare 端到端集成：从 supervisor 启动 → memory_search + research_agent 并行 → question_gen 收尾。

不连真实 MCP，全程 mock。验证状态机正确串联。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage


@pytest.mark.asyncio
async def test_prepare_full_flow_with_mcp_success():
    """完整路径：research_agent 成功 → 跳过 jd_analysis → question_gen 拿到 job_intel。"""
    from app.agents.prepare.graph import get_prepare_graph

    fake_report = {
        "job_interpretation": {
            "hard_requirements": ["分布式系统", "高并发"],
            "soft_requirements": [], "hidden_bonuses": [], "summary": "",
        },
        "resume_match": {"strengths": ["Python"], "gaps": ["缺分布式"]},
        "company_profile": {"summary": "字节核心业务", "tags": ["快节奏"]},
        "interview_qa": [],
        "salary_range": {},
        "prep_suggestions": [{"title": "3 天补分布式", "content": "DDIA"}],
    }

    # Mock supervisor LLM：先 → research_agent，再 → memory_search，再 → question_gen，再 → END
    sup_responses = iter([
        AIMessage(content='DECISION: {"next": "research_agent", "direction": "AI Agent 工程师", "reasoning": "有 JD"}'),
        AIMessage(content='DECISION: {"next": "memory_search", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "question_gen", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "END", "direction": "AI Agent 工程师", "reasoning": ""}'),
    ])

    # research_agent 内部 mock：1 轮 generate_position_report
    report_msg = AIMessage(content="", tool_calls=[{"name": "generate_position_report", "args": {"title": "x", "company": "y", "jd_summary": "", "requirements": [], "search_results": {}, "directions": ["x"]}, "id": "c1"}])
    stop_msg = AIMessage(content="完成")

    report_tool = MagicMock(); report_tool.name = "generate_position_report"; report_tool.ainvoke = AsyncMock(return_value=fake_report)

    # question_gen mock 输出 1 道题
    qg_chunk = MagicMock(); qg_chunk.content = '[{"id":1,"question":"Q1","category":"technical","focus_area":"分布式","priority":1}]'

    async def qg_astream(messages):
        yield qg_chunk

    with (
        patch("app.agents.prepare.nodes._llm") as mock_llm,
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[report_tool]),
        patch("app.agents.prepare.research_agent._chat_model") as mock_research_model,
        patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.prepare.nodes._get_resume_summary", new_callable=AsyncMock, return_value=None),
    ):
        # 区分不同节点的 astream 调用
        async def mock_astream_dispatch(messages):
            # 简单通过 prompt 里的关键词区分
            prompt = messages[0].content
            if "你是面试准备 Supervisor" in prompt:
                yield next(sup_responses)
            elif "你是专业面试出题官" in prompt:
                yield qg_chunk
            else:
                yield MagicMock(content="unknown")

        mock_llm.return_value.with_config.return_value.astream = mock_astream_dispatch
        
        # research_agent LLM
        rmodel = MagicMock()
        rmodel.bind_tools = MagicMock(return_value=rmodel)
        rmodel.ainvoke = AsyncMock(side_effect=[report_msg, stop_msg])
        mock_research_model.return_value = rmodel

        graph = get_prepare_graph()
        init_state = {
            "session_id": "s1",
            "user_id": "u1",
            "user_direction": "AI Agent 工程师",
            "jd_raw": "字节后端 JD 全文...",
        }
        final = await graph.ainvoke(init_state)

    assert final.get("job_intel") is not None
    assert final["job_intel"]["resume_match"]["gaps"] == ["缺分布式"]
    assert len(final.get("prepared_questions", [])) == 1
    assert "research_agent" in final.get("completed_tools", [])
    assert "memory_search" in final.get("completed_tools", [])


async def _async_gen(items):
    for x in items:
        yield x


@pytest.mark.asyncio
async def test_prepare_falls_back_to_jd_analysis_when_mcp_down():
    """MCP 不可用时（工具列表为空），Supervisor 路径走 jd_analysis 兜底，仍能产出题目。"""
    from app.agents.prepare.graph import get_prepare_graph
    from app.agents.prepare.nodes import SupervisorDecision

    sup_responses = iter([
        AIMessage(content='DECISION: {"next": "research_agent", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "memory_search", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "jd_analysis", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "question_gen", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "END", "direction": "AI Agent 工程师", "reasoning": ""}'),
    ])

    # jd_analysis 结果
    class JDOut:
        company = "字节"; role = "后端"; key_skills = ["Python"]; focus_areas = ["分布式"]; difficulty = "medium"

    # question_gen 结果
    qg_chunk = MagicMock(); qg_chunk.content = '[{"id":1,"question":"Q1","category":"technical","focus_area":"x","priority":1}]'

    with (
        patch("app.agents.prepare.nodes._llm") as mock_llm,
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.prepare.nodes._get_resume_summary", new_callable=AsyncMock, return_value=None),
    ):
        async def mock_astream_dispatch(messages):
            prompt = messages[0].content
            if "你是面试准备 Supervisor" in prompt:
                yield next(sup_responses)
            elif "你是专业面试出题官" in prompt:
                yield qg_chunk
            else:
                yield MagicMock(content="unknown")

        mock_llm.return_value.with_config.return_value.astream = mock_astream_dispatch
        
        # with_structured_output 调度
        def mock_structured_dispatch(model_class):
            m = MagicMock()
            if model_class.__name__ == "_JDContextModel":
                m.ainvoke = AsyncMock(return_value=JDOut())
            elif model_class == SupervisorDecision:
                # 即使 astream 失败也会调这里
                m.ainvoke = AsyncMock(return_value=SupervisorDecision(next="END"))
            return m

        mock_llm.return_value.with_structured_output.side_effect = mock_structured_dispatch

        graph = get_prepare_graph()
        init_state = {
            "session_id": "s2",
            "user_id": "u2",
            "user_direction": "AI Agent 工程师",
            "jd_raw": "字节后端 JD...",
        }
        final = await graph.ainvoke(init_state)

    assert final.get("job_intel") is None
    assert final.get("jd_context") is not None  # 兜底走了 jd_analysis
    assert len(final.get("prepared_questions", [])) == 1
