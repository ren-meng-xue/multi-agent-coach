"""chain 路由集成测试：master 出 chain → 节点顺序执行 → END。

不真调 LLM，把 master/evaluator/followup/ask_question/closing 全 patch。
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.interviewer.graph import build_interviewer_graph


@pytest.mark.asyncio
async def test_chain_evaluator_then_followup():
    """chain = ['evaluator', 'followup']：两个节点依次跑，到 END。"""
    state = {
        "session_id": "s1",
        "messages": [],
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }

    with patch("app.agents.interviewer.nodes.master_node",
               new=AsyncMock(return_value={**state, "chain": ["evaluator", "followup"]})), \
         patch("app.agents.interviewer.nodes.evaluator_node",
               new=AsyncMock(return_value={"turn_evaluations": [{"summary_score": 7.0}]})), \
         patch("app.agents.interviewer.nodes.followup_node",
               new=AsyncMock(return_value={"assistant_message": "追问内容"})):
        g = build_interviewer_graph()
        out = await g.ainvoke(state)
    assert out.get("assistant_message") == "追问内容"


@pytest.mark.asyncio
async def test_chain_just_followup_skips_evaluator():
    """chain = ['followup']：evaluator 不应被调用。"""
    state = {
        "session_id": "s2",
        "messages": [],
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }

    eval_mock = AsyncMock(return_value={"turn_evaluations": []})
    with patch("app.agents.interviewer.nodes.master_node",
               new=AsyncMock(return_value={**state, "chain": ["followup"]})), \
         patch("app.agents.interviewer.nodes.evaluator_node", new=eval_mock), \
         patch("app.agents.interviewer.nodes.followup_node",
               new=AsyncMock(return_value={"assistant_message": "拉回主题"})):
        g = build_interviewer_graph()
        out = await g.ainvoke(state)
    eval_mock.assert_not_called()
    assert out["assistant_message"] == "拉回主题"


@pytest.mark.asyncio
async def test_chain_closing_triggers_report():
    """chain = ['closing']：closing_node 后接 report_node。"""
    state = {
        "session_id": "s3",
        "messages": [],
        "question_count": 5,
        "total_questions": 5,
        "followup_count": 2,
        "max_followups": 2,
    }

    with patch("app.agents.interviewer.nodes.master_node",
               new=AsyncMock(return_value={**state, "chain": ["closing"]})), \
         patch("app.agents.interviewer.nodes.closing_node",
               new=AsyncMock(return_value={"assistant_message": "结束语", "stage": "closing"})), \
         patch("app.agents.interviewer.nodes.report_node",
               new=AsyncMock(return_value={"report": {"overall_score": 7.4}})):
        g = build_interviewer_graph()
        out = await g.ainvoke(state)
    assert out["report"]["overall_score"] == 7.4
    assert out["stage"] == "closing"


@pytest.mark.asyncio
async def test_chain_evaluator_then_ask_question():
    """chain = ['evaluator', 'ask_question']：进入下一题。"""
    state = {
        "session_id": "s4",
        "messages": [],
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 1,
        "max_followups": 2,
    }

    with patch("app.agents.interviewer.nodes.master_node",
               new=AsyncMock(return_value={**state, "chain": ["evaluator", "ask_question"]})), \
         patch("app.agents.interviewer.nodes.evaluator_node",
               new=AsyncMock(return_value={"turn_evaluations": [{"summary_score": 8.5}]})), \
         patch("app.agents.interviewer.nodes.ask_question_node",
               new=AsyncMock(return_value={"assistant_message": "第2题..."})):
        g = build_interviewer_graph()
        out = await g.ainvoke(state)
    assert out["assistant_message"] == "第2题..."
