"""简历摘要功能的 QA 测试：验证 summarize_resume 及 Coach 节点注入。"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.coach.nodes import load_memory_node, _generate_review_text, _generate_structured_plan
from app.agents.coach.state import CoachState
from app.services.resume_extractor import summarize_resume


# ─────────────────────────────────────────────
# summarize_resume 单元测试
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_summarize_resume_returns_string():
    """summarize_resume 返回非空字符串摘要。"""
    fake_content = MagicMock()
    fake_content.content = "  3年经验，Python后端工程师，熟悉FastAPI与PostgreSQL。  "

    with patch("app.services.resume_extractor.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=fake_content)

        result = await summarize_resume("某用户的简历内容..." * 10)

    assert result == "3年经验，Python后端工程师，熟悉FastAPI与PostgreSQL。"


@pytest.mark.asyncio
async def test_summarize_resume_truncates_long_input():
    """summarize_resume 对超长简历截断到 6000 字符。"""
    captured_prompts = []

    fake_content = MagicMock()
    fake_content.content = "摘要"

    async def capture_invoke(messages):
        captured_prompts.append(messages[0].content)
        return fake_content

    with patch("app.services.resume_extractor.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = capture_invoke

        long_text = "X" * 10000
        await summarize_resume(long_text)

    assert len(captured_prompts) == 1
    # prompt 中简历部分不超过 6000 字符
    assert "X" * 6001 not in captured_prompts[0]
    assert "X" * 6000 in captured_prompts[0]


# ─────────────────────────────────────────────
# load_memory_node 验证 resume_summary 读取
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_load_memory_node_reads_resume_summary():
    """load_memory_node 从 DB 读取 resume_summary 并放入 state。"""
    user_id = "user_test_abc"
    session_id = uuid4()

    mock_db = AsyncMock()

    # 模拟各查询的返回值
    count_result = MagicMock()
    count_result.scalar.return_value = 2

    mem_result = MagicMock()
    mem_result.scalar_one_or_none.return_value = None  # 无长期记忆

    session_result = MagicMock()
    session_row = MagicMock()
    session_row.report_json = {"score": 75}
    session_row.target_role = "后端工程师"
    session_result.scalar_one_or_none.return_value = session_row

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = "3年经验，Python后端，熟悉FastAPI。"

    mock_db.execute = AsyncMock(side_effect=[
        count_result,
        mem_result,
        session_result,
        user_result,
    ])

    state: CoachState = {
        "user_id": user_id,
        "session_id": session_id,
        "db": mock_db,
        "candidate_memory": None,
        "last_session_report": None,
        "target_role": None,
        "resume_summary": None,
        "review_text": "",
        "plan_json": None,
        "plan_id": None,
    }

    result = await load_memory_node(state)

    assert result["resume_summary"] == "3年经验，Python后端，熟悉FastAPI。"
    assert result["target_role"] == "后端工程师"


@pytest.mark.asyncio
async def test_load_memory_node_handles_no_resume_summary():
    """用户无简历时 resume_summary 为 None，不报错。"""
    mock_db = AsyncMock()

    count_result = MagicMock()
    count_result.scalar.return_value = 0

    mem_result = MagicMock()
    mem_result.scalar_one_or_none.return_value = None

    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = None

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = None  # 无摘要

    mock_db.execute = AsyncMock(side_effect=[
        count_result,
        mem_result,
        session_result,
        user_result,
    ])

    state: CoachState = {
        "user_id": "user_no_resume",
        "session_id": uuid4(),
        "db": mock_db,
        "candidate_memory": None,
        "last_session_report": None,
        "target_role": None,
        "resume_summary": None,
        "review_text": "",
        "plan_json": None,
        "plan_id": None,
    }

    result = await load_memory_node(state)
    assert result["resume_summary"] is None


# ─────────────────────────────────────────────
# LLM 上下文注入验证
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_review_text_injects_resume_summary():
    """_generate_review_text 在有简历摘要时将其注入 HumanMessage。"""
    captured_messages = []

    async def fake_astream(messages):
        captured_messages.extend(messages)
        yield MagicMock(content="这是复盘文本")

    mock_model = MagicMock()
    mock_model.astream = fake_astream

    state: CoachState = {
        "user_id": "u1",
        "session_id": uuid4(),
        "db": AsyncMock(),
        "candidate_memory": {"latest_level": "mid", "cumulative_signals": [], "weakness_tags": [], "total_sessions": 3},
        "last_session_report": {"score": 70},
        "target_role": "后端工程师",
        "resume_summary": "3年经验，Python后端，熟悉FastAPI与PostgreSQL。",
        "review_text": "",
        "plan_json": None,
        "plan_id": None,
    }

    with patch("app.agents.coach.nodes._chat_model", return_value=mock_model):
        # _chat_model() 返回的对象还要 .with_config()
        mock_model.with_config = MagicMock(return_value=mock_model)
        result = await _generate_review_text(state)

    assert result == "这是复盘文本"
    human_msg = captured_messages[1]  # index 0 = SystemMessage
    assert "候选人简历摘要" in human_msg.content
    assert "FastAPI与PostgreSQL" in human_msg.content


@pytest.mark.asyncio
async def test_generate_review_text_skips_resume_ctx_when_none():
    """无简历时 HumanMessage 中不包含简历摘要字段。"""
    captured_messages = []

    async def fake_astream(messages):
        captured_messages.extend(messages)
        yield MagicMock(content="复盘文本")

    mock_model = MagicMock()
    mock_model.astream = fake_astream
    mock_model.with_config = MagicMock(return_value=mock_model)

    state: CoachState = {
        "user_id": "u2",
        "session_id": uuid4(),
        "db": AsyncMock(),
        "candidate_memory": {"latest_level": None, "cumulative_signals": [], "weakness_tags": [], "total_sessions": 0},
        "last_session_report": {},
        "target_role": None,
        "resume_summary": None,
        "review_text": "",
        "plan_json": None,
        "plan_id": None,
    }

    with patch("app.agents.coach.nodes._chat_model", return_value=mock_model):
        await _generate_review_text(state)

    human_msg = captured_messages[1]
    assert "候选人简历摘要" not in human_msg.content
