"""Chief ReAct loop 路由测试。"""
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.interviewer.chief import chief_respond, chief_think
from app.agents.interviewer.graph import build_interviewer_graph


@pytest.mark.asyncio
async def test_chief_loop_execute_then_respond():
    """chief_think -> chief_execute -> chief_think -> chief_respond -> END。"""
    state = {
        "session_id": "s1",
        "messages": [],
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }

    think = AsyncMock(
        side_effect=[
            {
                **state,
                "chief_messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "evaluate_answer", "args": {}, "id": "eval"},
                            {"name": "design_question", "args": {"focus": "dual"}, "id": "design"},
                        ],
                    )
                ],
                "chief_iteration": 0,
            },
            {**state, "chief_messages": [AIMessage(content="直接回复")], "chief_iteration": 1},
        ]
    )
    execute = AsyncMock(return_value={**state, "chief_iteration": 1, "evaluator_report": {}})
    respond = AsyncMock(return_value={"assistant_message": "追问内容", "stage": "interview"})

    with patch("app.agents.interviewer.chief.chief_think", new=think), \
        patch("app.agents.interviewer.chief.chief_execute", new=execute), \
        patch("app.agents.interviewer.chief.chief_respond", new=respond):
        g = build_interviewer_graph()
        out = await g.ainvoke(state)

    assert execute.await_count == 1
    assert respond.await_count == 1
    assert out.get("assistant_message") == "追问内容"


@pytest.mark.asyncio
async def test_chief_direct_respond_skips_execute():
    """chief_think 直接 respond 时不调用工具执行节点。"""
    state = {
        "session_id": "s2",
        "messages": [],
        "question_count": 1,
        "total_questions": 5,
    }

    execute = AsyncMock(return_value={})
    with patch(
        "app.agents.interviewer.chief.chief_think",
        new=AsyncMock(return_value={**state, "chief_messages": [AIMessage(content="直接回复")]}),
    ), patch("app.agents.interviewer.chief.chief_execute", new=execute), patch(
        "app.agents.interviewer.chief.chief_respond",
        new=AsyncMock(return_value={"assistant_message": "直接回复", "stage": "interview"}),
    ):
        g = build_interviewer_graph()
        out = await g.ainvoke(state)

    execute.assert_not_awaited()
    assert out["assistant_message"] == "直接回复"


@pytest.mark.asyncio
async def test_chief_closing_triggers_report():
    """chief_respond 返回 closing 后接 report_node。"""
    state = {
        "session_id": "s3",
        "messages": [],
        "question_count": 5,
        "total_questions": 5,
    }

    with patch(
        "app.agents.interviewer.chief.chief_think",
        new=AsyncMock(return_value={**state, "chief_messages": [AIMessage(content="直接回复")]}),
    ), patch(
        "app.agents.interviewer.chief.chief_respond",
        new=AsyncMock(return_value={"assistant_message": "结束语", "stage": "closing"}),
    ), patch(
        "app.agents.interviewer.nodes.report_node",
        new=AsyncMock(return_value={"report": {"overall_score": 7.4}}),
    ):
        g = build_interviewer_graph()
        out = await g.ainvoke(state)

    assert out["report"]["overall_score"] == 7.4
    assert out["stage"] == "closing"


@pytest.mark.asyncio
async def test_chief_low_score_without_missing_dimensions_still_followups():
    """低分但 missing_dimensions 为空时，不能推进到下一题。"""
    state = {
        "session_id": "s4",
        "messages": [HumanMessage(content="只做过一点缓存优化，没有更多细节。")],
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "evaluator_report": {
            "scoring": {
                "summary_score": 5.0,
                "missing_dimensions": [],
            },
            "report_text": "回答过浅，缺少具体方案和结果。",
        },
        "designer_dual_output": {
            "followup_question": "请补充具体方案和结果？",
            "new_question": "新题？",
            "source": "llm",
        },
    }

    with patch(
        "app.agents.interviewer.chief._chat_model",
        return_value=type(
            "FakeModel",
            (),
            {
                "bind_tools": lambda self, _tools: self,
                "with_config": lambda self, **_kwargs: self,
                "ainvoke": AsyncMock(return_value=AIMessage(content="选择追问。")),
            },
        )(),
    ):
        routed = await chief_think(state)

    assert routed["designer_output"]["question_text"] == "请补充具体方案和结果？"

    responded = await chief_respond({
        **state,
        "designer_output": {"question_text": "请补充你当时具体改了哪些缓存策略？"},
    })

    assert "question_count" not in responded
    assert responded["followup_count"] == 1


@pytest.mark.asyncio
async def test_chief_first_turn_responds_after_designer_without_evaluating_empty_answer():
    """首轮启动已经拿到 Designer 输出后，应直接回复首题，不评估空回答。"""
    state = {
        "session_id": "s5",
        "messages": [],
        "question_count": 0,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "chief_iteration": 1,
        "designer_output": {
            "question_text": "请讲讲你最近做过的一个 AI 应用项目。",
            "question_category": "project",
            "focus_area": "project_scope",
        },
        "evaluator_report": None,
    }

    with patch(
        "app.agents.interviewer.chief._chat_model",
        return_value=type(
            "FakeModel",
            (),
            {
                "bind_tools": lambda self, _tools: self,
                "with_config": lambda self, **_kwargs: self,
                "ainvoke": AsyncMock(return_value=AIMessage(content="直接回复首题。")),
            },
        )(),
    ):
        routed = await chief_think(state)

    assert not routed["chief_messages"][-1].tool_calls
