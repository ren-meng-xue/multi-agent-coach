"""验证教练 Agent 各节点逻辑。"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.coach.nodes import (
    CoachPlanSchema,
    load_memory_node,
    persist_node,
    plan_node,
    review_node,
)


@pytest.fixture
def mock_db():
    return MagicMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_load_memory_node(mock_db):
    user_id = "user_test_1"
    session_id = uuid4()
    
    # Mock CandidateMemory 记录
    mock_mem = MagicMock()
    mock_mem.latest_level = "junior"
    mock_mem.cumulative_signals = ["s1"]
    mock_mem.weakness_tags = [{"tag": "w1", "count": 1}]
    mock_mem.total_sessions = 1
    
    # Mock InterviewSession 记录
    mock_session = MagicMock()
    mock_session.report_json = {"overall_score": 4.0}
    
    # 设置 mock_db.execute 返回不同的结果
    mock_res_count = MagicMock()
    mock_res_count.scalar.return_value = 1

    mock_res_mem = MagicMock()
    mock_res_mem.scalar_one_or_none.return_value = mock_mem

    mock_res_session = MagicMock()
    mock_res_session.scalar_one_or_none.return_value = mock_session

    mock_res_user = MagicMock()
    mock_res_user.scalar_one_or_none.return_value = "3年Python后端经验，熟悉FastAPI。"

    mock_db.execute.side_effect = [mock_res_count, mock_res_mem, mock_res_session, mock_res_user]
    
    state = {"db": mock_db, "user_id": user_id, "session_id": session_id}
    result = await load_memory_node(state)
    
    assert result["candidate_memory"]["latest_level"] == "junior"
    assert result["last_session_report"]["overall_score"] == 4.0

@pytest.mark.asyncio
async def test_review_node_calls_llm():
    state = {
        "candidate_memory": {"latest_level": "junior"},
        "last_session_report": {"overall_score": 4.0}
    }
    with patch("app.agents.coach.nodes._generate_review_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "这是复盘内容"
        result = await review_node(state)
        assert result["review_text"] == "这是复盘内容"

@pytest.mark.asyncio
async def test_plan_node_structured_output():
    state = {"review_text": "...", "candidate_memory": {}}
    mock_plan = CoachPlanSchema(
        summary="总结",
        strengths=["亮点"],
        weaknesses=["短板"],
        next_focus_areas=["方向"],
        recommended_role="中级",
        recommended_question_types=["场景"]
    )
    with patch("app.agents.coach.nodes._generate_structured_plan", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_plan
        result = await plan_node(state)
        assert result["plan_json"]["summary"] == "总结"

@pytest.mark.asyncio
async def test_persist_node_writes_to_db(mock_db):
    user_id = "user_1"
    sid = uuid4()
    plan_id = uuid4()
    
    state = {
        "db": mock_db,
        "user_id": user_id,
        "session_id": sid,
        "plan_json": {"summary": "总结"}
    }
    
    # 模拟 DB 查询：返回 None (表示无已有计划)
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_res)
    
    # 模拟 SQLAlchemy 对象的行为
    def mock_add(obj):
        obj.id = plan_id
        
    mock_db.add.side_effect = mock_add
    
    result = await persist_node(state)
    assert result["plan_id"] == plan_id
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
