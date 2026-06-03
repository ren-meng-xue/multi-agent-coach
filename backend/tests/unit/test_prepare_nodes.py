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

    state: PrepareState = {"user_id": "user_123", "user_direction": "AI Agent 工程师"}

    with (
        patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=mock_sessions),
        patch("app.agents.prepare.nodes._get_resume_summary", new_callable=AsyncMock, return_value=None),
    ):
        result = await memory_search_node(state)

    assert len(result["weak_areas"]) > 0
    assert "memory_search" in result["completed_tools"]


@pytest.mark.asyncio
async def test_memory_search_empty_when_no_history():
    """无历史时返回空列表，不报错。"""
    from app.agents.prepare.nodes import memory_search_node

    state: PrepareState = {"user_id": "new_user"}

    with (
        patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.prepare.nodes._get_resume_summary", new_callable=AsyncMock, return_value=None),
    ):
        result = await memory_search_node(state)

    assert result["weak_areas"] == []
    assert result["user_background"] is None
    assert "memory_search" in result["completed_tools"]


@pytest.mark.asyncio
async def test_memory_search_uses_resume_summary_when_background_missing():
    """当前请求未带背景时，应从用户简历摘要兜底填入 user_background。"""
    from app.agents.prepare.nodes import memory_search_node

    state: PrepareState = {"user_id": "new_user", "user_background": None}

    with (
        patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=[]),
        patch(
            "app.agents.prepare.nodes._get_resume_summary",
            new_callable=AsyncMock,
            return_value="3年 Python 后端经验，做过 RAG 和 Agent 项目。",
        ) as mock_resume,
    ):
        result = await memory_search_node(state)

    mock_resume.assert_awaited_once_with("new_user")
    assert result["weak_areas"] == []
    assert result["user_background"] == "3年 Python 后端经验，做过 RAG 和 Agent 项目。"
    assert "memory_search" in result["completed_tools"]


@pytest.mark.asyncio
async def test_memory_search_keeps_explicit_background():
    """请求已带背景时，不应再用简历摘要覆盖用户本次输入。"""
    from app.agents.prepare.nodes import memory_search_node

    state: PrepareState = {"user_id": "u1", "user_background": "本次重点准备 LangGraph 项目"}

    with (
        patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.prepare.nodes._get_resume_summary", new_callable=AsyncMock) as mock_resume,
    ):
        result = await memory_search_node(state)

    mock_resume.assert_not_awaited()
    assert result["user_background"] == "本次重点准备 LangGraph 项目"
    assert "memory_search" in result["completed_tools"]


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
    assert "jd_analysis" in result["completed_tools"]


@pytest.mark.asyncio
async def test_jd_analysis_skips_when_no_jd():
    """无 JD 时跳过，不调 LLM，jd_context 为 None。"""
    from app.agents.prepare.nodes import jd_analysis_node

    state: PrepareState = {"user_id": "u1", "jd_raw": None}
    result = await jd_analysis_node(state)
    assert result.get("jd_context") is None
    assert "jd_analysis" in result["completed_tools"]


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
        "user_background": "做过一个多 Agent 面试教练项目",
        "weak_areas": ["量化结果欠缺"],
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
    assert "question_gen" in result["completed_tools"]


@pytest.mark.asyncio
async def test_question_gen_injects_user_background_into_prompt():
    from app.agents.prepare.nodes import question_gen_node

    state: PrepareState = {
        "user_id": "u1",
        "direction": "AI Agent 工程师",
        "user_direction": "AI Agent 工程师",
        "user_background": "3年 Python 后端经验，做过 RAG 和 Agent 项目。",
        "weak_areas": [],
        "jd_context": None,
    }

    mock_content = '[{"id":1,"question":"Q1","category":"technical","focus_area":"RAG","priority":1}]'
    captured: dict[str, str] = {}

    async def mock_astream(messages):
        captured["prompt"] = messages[0].content
        mock_chunk = MagicMock()
        mock_chunk.content = mock_content
        yield mock_chunk

    with patch("app.agents.prepare.nodes._llm") as mock_llm:
        mock_llm.return_value.with_config.return_value.astream = mock_astream
        await question_gen_node(state)

    assert "候选人背景/简历摘要：3年 Python 后端经验，做过 RAG 和 Agent 项目。" in captured["prompt"]


@pytest.mark.asyncio
async def test_question_gen_weak_areas_first():
    """薄弱点相关题目 priority 应为最低数值（最高优先级）。"""
    from app.agents.prepare.nodes import question_gen_node

    state: PrepareState = {
        "user_id": "u1",
        "direction": "后端工程师",
        "user_direction": "后端工程师",
        "weak_areas": ["量化结果欠缺", "系统设计薄弱"],
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


@pytest.mark.asyncio
async def test_supervisor_detects_direction_from_user_input():
    from app.agents.prepare.nodes import supervisor_node

    state: PrepareState = {
        "user_id": "u1",
        "user_direction": "AI Agent 工程师",
        "jd_raw": None,
        "weak_areas": [],
    }

    mock_decision = MagicMock()
    mock_decision.next = "question_gen"
    mock_decision.direction = "AI Agent 工程师"
    mock_decision.reasoning = "已提供明确方向"

    with patch("app.agents.prepare.nodes._llm") as mock_llm:
        # reasoning stream
        mock_stream = MagicMock()
        mock_stream.content = "• 找到方向"
        mock_llm.return_value.with_config.return_value.astream = MagicMock(
            return_value=aiter([mock_stream])
        )
        # decision structured output
        mock_llm.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_decision
        )
        result = await supervisor_node(state)

    assert result["direction"] == "AI Agent 工程师"
    assert result["next_action"] == "question_gen"
    assert result["iteration_count"] == 1


@pytest.mark.asyncio
async def test_supervisor_sets_need_direction_when_no_input():
    from app.agents.prepare.nodes import supervisor_node

    state: PrepareState = {
        "user_id": "new_user",
        "user_direction": None,
        "jd_raw": None,
        "weak_areas": [],
    }

    mock_decision = MagicMock()
    mock_decision.next = "need_direction"
    mock_decision.direction = ""
    mock_decision.reasoning = "缺少方向"

    with patch("app.agents.prepare.nodes._llm") as mock_llm:
        mock_stream = MagicMock()
        mock_stream.content = "• 未找到方向"
        mock_llm.return_value.with_config.return_value.astream = MagicMock(
            return_value=aiter([mock_stream])
        )
        mock_llm.return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=mock_decision
        )
        result = await supervisor_node(state)

    assert result["need_direction"] is True
    assert result["next_action"] == "need_direction"


@pytest.mark.asyncio
async def test_supervisor_prevents_loop():
    from app.agents.prepare.nodes import supervisor_node

    state: PrepareState = {
        "user_id": "u1",
        "iteration_count": 6,
    }

    result = await supervisor_node(state)
    assert result["next_action"] == "END"
    assert result["iteration_count"] == 7

@pytest.mark.asyncio
async def test_question_gen_uses_job_intel_when_available():
    """question_gen 应优先用 job_intel.job_interpretation 的 hard_requirements / focus 出题。"""
    from app.agents.prepare.nodes import question_gen_node

    state: PrepareState = {
        "user_id": "u1",
        "direction": "AI Agent 工程师",
        "user_direction": "AI Agent 工程师",
        "user_background": "3 年 Python",
        "weak_areas": [],
        "jd_context": None,
        "job_intel": {
            "job_interpretation": {
                "hard_requirements": ["分布式系统", "高并发"],
                "soft_requirements": ["快节奏适应"],
                "hidden_bonuses": ["LangGraph 经验"],
                "summary": "字节核心业务",
            },
            "resume_match": {"strengths": ["Python"], "gaps": ["缺分布式"]},
        },
    }

    mock_content = '[{"id":1,"question":"Q1","category":"technical","focus_area":"分布式","priority":1}]'
    captured: dict[str, str] = {}

    async def mock_astream(messages):
        captured["prompt"] = messages[0].content
        mock_chunk = MagicMock()
        mock_chunk.content = mock_content
        yield mock_chunk

    with patch("app.agents.prepare.nodes._llm") as mock_llm:
        mock_llm.return_value.with_config.return_value.astream = mock_astream
        await question_gen_node(state)

    # 验证 job_intel 的硬要求和 gap 进了出题 prompt
    assert "分布式系统" in captured["prompt"]
    assert "缺分布式" in captured["prompt"]
