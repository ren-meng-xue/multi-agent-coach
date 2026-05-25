# backend/tests/unit/test_prepare_nodes.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.prepare.state import PrepareState


@pytest.mark.asyncio
async def test_memory_search_returns_weak_areas_from_history():
    """有历史面试时应返回薄弱点列表。"""
    from app.agents.prepare.nodes import memory_search_node

    mock_sessions = [
        MagicMock(
            report={"technical_depth": 2, "quantified_results": 1},
            target_role="AI Agent 工程师",
        )
    ]
    mock_stories = [
        MagicMock(
            title="LangGraph 工单系统",
            role="AI 工程师",
            tags=["LangGraph", "Agent"],
            content_json={"situation": "...", "task": "...", "action": "...", "result": "..."},
        )
    ]

    state: PrepareState = {"user_id": "user_123", "user_direction": "AI Agent 工程师"}

    with patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=mock_sessions), \
         patch("app.agents.prepare.nodes._get_user_stories", new_callable=AsyncMock, return_value=mock_stories):
        result = await memory_search_node(state)

    assert len(result["weak_areas"]) > 0
    assert len(result["star_stories"]) == 1
    assert result["star_stories"][0]["title"] == "LangGraph 工单系统"


@pytest.mark.asyncio
async def test_memory_search_empty_when_no_history():
    """无历史时返回空列表，不报错。"""
    from app.agents.prepare.nodes import memory_search_node

    state: PrepareState = {"user_id": "new_user"}

    with patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=[]), \
         patch("app.agents.prepare.nodes._get_user_stories", new_callable=AsyncMock, return_value=[]):
        result = await memory_search_node(state)

    assert result["weak_areas"] == []
    assert result["star_stories"] == []


@pytest.mark.asyncio
async def test_jd_analysis_returns_jd_context():
    """有 JD 文本时应返回结构化 JDContext。"""
    from app.agents.prepare.nodes import jd_analysis_node

    state: PrepareState = {
        "user_id": "u1",
        "jd_raw": "招聘高级后端工程师，要求熟悉 Python、分布式系统、Kafka",
        "user_direction": "后端工程师",
    }

    mock_output = MagicMock()
    mock_output.company = "字节跳动"
    mock_output.role = "高级后端工程师"
    mock_output.key_skills = ["Python", "分布式系统", "Kafka"]
    mock_output.focus_areas = ["系统设计", "高并发"]
    mock_output.difficulty = "hard"

    with patch("app.agents.prepare.nodes._llm") as mock_llm:
        mock_llm.return_value.with_structured_output.return_value.ainvoke = AsyncMock(return_value=mock_output)
        result = await jd_analysis_node(state)

    assert result["jd_context"] is not None
    assert result["jd_context"]["key_skills"] == ["Python", "分布式系统", "Kafka"]
    assert result["jd_context"]["difficulty"] == "hard"


@pytest.mark.asyncio
async def test_jd_analysis_skips_when_no_jd():
    """无 JD 时跳过，不调 LLM，jd_context 为 None。"""
    from app.agents.prepare.nodes import jd_analysis_node

    state: PrepareState = {"user_id": "u1", "jd_raw": None}
    result = await jd_analysis_node(state)
    assert result.get("jd_context") is None
