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


# 测试辅助：模拟 async iterator
async def aiter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_question_gen_returns_5_questions():
    from app.agents.prepare.nodes import question_gen_node

    state: PrepareState = {
        "user_id": "u1",
        "direction": "AI Agent 工程师",
        "user_direction": "AI Agent 工程师",
        "weak_areas": ["量化结果欠缺"],
        "star_stories": [],
        "jd_context": None,
    }

    mock_content = '[{"id":1,"question":"Q1","category":"technical","focus_area":"RAG","priority":1},{"id":2,"question":"Q2","category":"behavioral","focus_area":"量化","priority":1},{"id":3,"question":"Q3","category":"technical","focus_area":"Agent","priority":2},{"id":4,"question":"Q4","category":"system_design","focus_area":"架构","priority":3},{"id":5,"question":"Q5","category":"technical","focus_area":"LangGraph","priority":3}]'

    with patch("app.agents.prepare.nodes._llm") as mock_llm:
        mock_chunk = MagicMock()
        mock_chunk.content = mock_content
        mock_llm.return_value.with_config.return_value.astream = MagicMock(
            return_value=aiter([mock_chunk])
        )
        result = await question_gen_node(state)

    assert len(result["prepared_questions"]) == 5
    assert result["prepared_questions"][0]["priority"] == 1


@pytest.mark.asyncio
async def test_question_gen_weak_areas_first():
    """薄弱点相关题目 priority 应为最低数值（最高优先级）。"""
    from app.agents.prepare.nodes import question_gen_node

    state: PrepareState = {
        "user_id": "u1",
        "direction": "后端工程师",
        "user_direction": "后端工程师",
        "weak_areas": ["量化结果欠缺", "系统设计薄弱"],
        "star_stories": [],
        "jd_context": None,
    }

    mock_content = '[{"id":1,"question":"量化题","category":"behavioral","focus_area":"量化","priority":1},{"id":2,"question":"系统设计题","category":"system_design","focus_area":"设计","priority":1},{"id":3,"question":"Q3","category":"technical","focus_area":"Python","priority":3},{"id":4,"question":"Q4","category":"technical","focus_area":"DB","priority":3},{"id":5,"question":"Q5","category":"behavioral","focus_area":"团队","priority":4}]'

    with patch("app.agents.prepare.nodes._llm") as mock_llm:
        mock_chunk = MagicMock()
        mock_chunk.content = mock_content
        mock_llm.return_value.with_config.return_value.astream = MagicMock(
            return_value=aiter([mock_chunk])
        )
        result = await question_gen_node(state)

    priorities = [q["priority"] for q in result["prepared_questions"]]
    assert priorities[0] <= priorities[-1]  # 第一题优先级最高
