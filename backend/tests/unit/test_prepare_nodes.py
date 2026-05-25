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
