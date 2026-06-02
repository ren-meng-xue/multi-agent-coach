"""Chief Interviewer tool-calling 推理链测试。"""
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.interviewer.chief import (
    _answer_is_sufficient,
    _followup_focus,
    _pick_question,
    chief_execute,
    chief_think,
    route_after_chief_respond,
    route_after_chief_think,
)


class _FakeToolCallingModel:
    def __init__(self, response: AIMessage):
        self.response = response
        self.bound_tools = []

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def with_config(self, **_kwargs):
        return self

    async def ainvoke(self, _messages):
        return self.response


def _tool_call(name: str, args: dict | None = None, call_id: str = "tc1") -> dict:
    return {"name": name, "args": args or {}, "id": call_id}


class TestChiefThinkDecisions:
    @pytest.mark.asyncio
    async def test_first_turn_accepts_design_question_tool_call(self):
        response = AIMessage(
            content="首轮启动，先设计第一题。",
            tool_calls=[_tool_call("design_question", {"focus": "new_question"})],
        )
        with patch("app.agents.interviewer.chief._chat_model", return_value=_FakeToolCallingModel(response)):
            result = await chief_think({"question_count": 0, "messages": [], "session_id": "s1"})

        last = result["chief_messages"][-1]
        assert isinstance(last, AIMessage)
        assert last.tool_calls[0]["name"] == "design_question"
        assert last.tool_calls[0]["args"]["focus"] == "new_question"

    @pytest.mark.asyncio
    async def test_answer_turn_accepts_parallel_eval_and_design_tool_calls(self):
        response = AIMessage(
            content="并行评估和准备双方案。",
            tool_calls=[
                _tool_call("evaluate_answer", call_id="eval"),
                _tool_call("design_question", {"focus": "dual"}, call_id="design"),
            ],
        )
        state = {
            "question_count": 1,
            "messages": [HumanMessage(content="我用了 Redis 做缓存。")],
            "session_id": "s1",
            "evaluator_report": None,
            "designer_output": None,
        }
        with patch("app.agents.interviewer.chief._chat_model", return_value=_FakeToolCallingModel(response)):
            result = await chief_think(state)

        calls = result["chief_messages"][-1].tool_calls
        assert [tc["name"] for tc in calls] == ["evaluate_answer", "design_question"]
        assert calls[1]["args"]["focus"] == "dual"

    @pytest.mark.asyncio
    async def test_first_turn_without_tool_call_synthesizes_design_tool(self):
        response = AIMessage(content="首轮启动。")
        with patch("app.agents.interviewer.chief._chat_model", return_value=_FakeToolCallingModel(response)):
            result = await chief_think({"question_count": 0, "messages": [], "session_id": "s1"})

        calls = result["chief_messages"][-1].tool_calls
        assert calls[0]["name"] == "design_question"
        assert calls[0]["args"] == {"focus": "new_question"}
        assert calls[0]["id"] == "fallback_design"
        assert route_after_chief_think(result) == "chief_execute"

    @pytest.mark.asyncio
    async def test_answer_turn_without_tool_call_synthesizes_eval_and_design_tools(self):
        response = AIMessage(content="继续分析。")
        state = {
            "question_count": 1,
            "messages": [HumanMessage(content="我用了 Redis 做缓存。")],
            "session_id": "s1",
        }
        with patch("app.agents.interviewer.chief._chat_model", return_value=_FakeToolCallingModel(response)):
            result = await chief_think(state)

        calls = result["chief_messages"][-1].tool_calls
        assert [tc["name"] for tc in calls] == ["evaluate_answer", "design_question"]
        assert calls[1]["args"] == {"focus": "dual"}
        assert route_after_chief_think(result) == "chief_execute"

    @pytest.mark.asyncio
    async def test_final_answer_without_tool_call_synthesizes_eval_only(self):
        response = AIMessage(content="先评估最后一题。")
        state = {
            "question_count": 5,
            "total_questions": 5,
            "messages": [HumanMessage(content="最后一题回答。")],
            "session_id": "s1",
        }
        with patch("app.agents.interviewer.chief._chat_model", return_value=_FakeToolCallingModel(response)):
            result = await chief_think(state)

        calls = result["chief_messages"][-1].tool_calls
        assert [tc["name"] for tc in calls] == ["evaluate_answer"]
        assert route_after_chief_think(result) == "chief_execute"

    @pytest.mark.asyncio
    async def test_final_sufficient_evaluation_without_tool_call_routes_to_respond(self):
        response = AIMessage(content="题目已完成，准备收尾。")
        state = {
            "question_count": 5,
            "total_questions": 5,
            "messages": [HumanMessage(content="最后一题回答。")],
            "evaluator_report": {"scoring": {"summary_score": 8.0, "missing_dimensions": []}},
            "session_id": "s1",
        }
        with patch("app.agents.interviewer.chief._chat_model", return_value=_FakeToolCallingModel(response)):
            result = await chief_think(state)

        assert result["chief_messages"][-1].tool_calls == []
        assert route_after_chief_think(result) == "chief_respond"

    @pytest.mark.asyncio
    async def test_parallel_results_ready_low_score_picks_followup(self):
        state = {
            "question_count": 1,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
            "messages": [HumanMessage(content="我做了缓存优化")],
            "evaluator_report": {
                "scoring": {"summary_score": 5.0, "missing_dimensions": ["量化结果"]}
            },
            "designer_dual_output": {
                "followup_question": "请量化优化效果？",
                "new_question": "请讲一个系统设计取舍？",
                "source": "llm",
            },
            "designer_output": None,
            "session_id": "s1",
        }
        response = AIMessage(content="结果就绪，选择追问。")
        with patch("app.agents.interviewer.chief._chat_model", return_value=_FakeToolCallingModel(response)):
            result = await chief_think(state)

        assert result["designer_output"]["question_text"] == "请量化优化效果？"
        assert result["designer_dual_output"] is None

    @pytest.mark.asyncio
    async def test_parallel_results_ready_high_score_picks_new_question(self):
        state = {
            "question_count": 1,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
            "messages": [HumanMessage(content="我做了缓存优化，命中率提升 30%。")],
            "evaluator_report": {"scoring": {"summary_score": 8.0, "missing_dimensions": []}},
            "designer_dual_output": {
                "followup_question": "请补充约束？",
                "new_question": "请讲一个系统设计取舍？",
                "source": "llm",
            },
            "designer_output": None,
            "session_id": "s1",
        }
        response = AIMessage(content="结果就绪，选择新题。")
        with patch("app.agents.interviewer.chief._chat_model", return_value=_FakeToolCallingModel(response)):
            result = await chief_think(state)

        assert result["designer_output"]["question_text"] == "请讲一个系统设计取舍？"

    @pytest.mark.asyncio
    async def test_chief_execute_runs_parallel_tool_calls(self):
        eval_result = {
            "scoring": {"summary_score": 5.0, "missing_dimensions": ["量化"]},
            "updated_profile": {},
        }
        dual_result = {"followup_question": "追问？", "new_question": "新题？", "source": "llm"}
        state = {
            "session_id": "s1",
            "user_id": "u1",
            "target_role": "后端工程师",
            "chief_iteration": 0,
            "turn_evaluations": [],
            "messages": [HumanMessage(content="我做了缓存优化")],
            "chief_messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        _tool_call("evaluate_answer", call_id="eval"),
                        _tool_call("design_question", {"focus": "dual"}, call_id="design"),
                    ],
                )
            ],
        }
        with patch("app.agents.interviewer.chief._execute_evaluate", new=AsyncMock(return_value=eval_result)), patch(
            "app.agents.interviewer.chief._execute_design_dual", new=AsyncMock(return_value=dual_result)
        ):
            result = await chief_execute(state)

        assert result["evaluator_report"] == eval_result
        assert result["designer_dual_output"] == dual_result
        assert result["chief_iteration"] == 1
        assert len(result["chief_messages"]) == 3


class TestAnswerSufficiency:
    def test_high_score_no_missing_is_sufficient(self):
        report = {"scoring": {"summary_score": 7.5, "missing_dimensions": []}}
        assert _answer_is_sufficient(report) is True

    def test_below_7_is_not_sufficient(self):
        report = {"scoring": {"summary_score": 6.9, "missing_dimensions": []}}
        assert _answer_is_sufficient(report) is False

    def test_none_report_is_not_sufficient(self):
        assert _answer_is_sufficient(None) is False

    def test_followup_focus_uses_missing_dimensions(self):
        report = {"scoring": {"missing_dimensions": ["量化", "权衡"]}}
        assert "量化" in _followup_focus(report)

    def test_pick_question_low_score_returns_followup(self):
        eval_report = {"scoring": {"summary_score": 5.0, "missing_dimensions": ["量化"]}}
        dual = {"followup_question": "追问？", "new_question": "新题？"}
        assert _pick_question(eval_report, dual, followup_count=0, max_followups=2) == "追问？"

    def test_pick_question_high_score_returns_new_question(self):
        eval_report = {"scoring": {"summary_score": 8.0, "missing_dimensions": []}}
        dual = {"followup_question": "追问？", "new_question": "新题？"}
        assert _pick_question(eval_report, dual, followup_count=0, max_followups=2) == "新题？"

    def test_pick_question_max_followups_forces_new_question(self):
        eval_report = {"scoring": {"summary_score": 4.0, "missing_dimensions": ["量化"]}}
        dual = {"followup_question": "追问？", "new_question": "新题？"}
        assert _pick_question(eval_report, dual, followup_count=2, max_followups=2) == "新题？"


class TestRouteAfterChiefThink:
    def test_tool_calls_route_to_execute(self):
        state = {"chief_messages": [AIMessage(content="", tool_calls=[_tool_call("design_question")])]}
        assert route_after_chief_think(state) == "chief_execute"

    def test_no_tool_calls_route_to_respond(self):
        state = {"chief_messages": [AIMessage(content="直接回复")]}
        assert route_after_chief_think(state) == "chief_respond"

    def test_missing_messages_route_to_respond(self):
        assert route_after_chief_think({}) == "chief_respond"


class TestRouteAfterChiefRespond:
    def test_closing_stage_routes_to_report(self):
        assert route_after_chief_respond({"stage": "closing"}) == "report"

    def test_interview_stage_routes_to_end(self):
        assert route_after_chief_respond({"stage": "interview"}) == "__end__"

    def test_missing_stage_routes_to_end(self):
        assert route_after_chief_respond({}) == "__end__"
