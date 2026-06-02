"""Chief Interviewer 安全边界测试：终止词、迭代上限、工具异常恢复。"""
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.interviewer.chief import (
    MAX_CHIEF_ITERATIONS,
    _wants_to_end,
    chief_execute,
    chief_think,
    route_after_chief_think,
)


class _FakeToolCallingModel:
    def __init__(self, response: AIMessage):
        self.response = response

    def bind_tools(self, _tools):
        return self

    def with_config(self, **_kwargs):
        return self

    async def ainvoke(self, _messages):
        return self.response


def _tool_call(name: str, args: dict | None = None, call_id: str = "tc1") -> dict:
    return {"name": name, "args": args or {}, "id": call_id}


class TestTerminationKeywords:
    def test_end_keywords_detected(self):
        for kw in ("结束", "不面了", "拜拜", "退出", "算了", "停止"):
            assert _wants_to_end(kw) is True

    def test_long_message_not_end(self):
        assert _wants_to_end("我觉得这个结束了，但我还想补充一下我的项目经历") is False

    def test_normal_answer_not_end(self):
        assert _wants_to_end("我用了微服务架构来分离关注点，具体做法是……") is False

    @pytest.mark.asyncio
    async def test_end_intent_does_not_route_to_execute_when_llm_calls_no_tools(self):
        response = AIMessage(content="候选人表达结束意图，准备收尾。")
        state = {"question_count": 2, "messages": [HumanMessage(content="结束吧")], "session_id": "s1"}
        with patch("app.agents.interviewer.chief._chat_model", return_value=_FakeToolCallingModel(response)):
            result = await chief_think(state)
        assert route_after_chief_think(result) == "chief_respond"


class TestIterationCap:
    @pytest.mark.asyncio
    async def test_iteration_increments_per_execute(self):
        state = {
            "session_id": "s1",
            "user_id": "u1",
            "target_role": "后端工程师",
            "chief_iteration": 0,
            "messages": [],
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
        with patch(
            "app.agents.interviewer.chief.run_evaluator",
            new_callable=AsyncMock,
            return_value={
                "scoring": {"summary_score": 7.0, "missing_dimensions": []},
                "report_text": "ok",
                "updated_profile": {},
            },
        ), patch(
            "app.agents.interviewer.chief.run_designer_dual",
            new_callable=AsyncMock,
            return_value={"followup_question": "追问？", "new_question": "新题？", "source": "llm"},
        ):
            result = await chief_execute(state)
        assert result["chief_iteration"] == 1

    @pytest.mark.asyncio
    async def test_at_max_iterations_chief_think_has_no_tool_calls(self):
        state = {
            "question_count": 2,
            "chief_iteration": MAX_CHIEF_ITERATIONS,
            "messages": [HumanMessage(content="回答")],
            "evaluator_report": None,
            "designer_output": None,
            "session_id": "s1",
        }
        result = await chief_think(state)
        assert route_after_chief_think(result) == "chief_respond"

    @pytest.mark.asyncio
    async def test_llm_exception_on_first_turn_falls_back_to_design_tool(self):
        state = {"question_count": 0, "messages": [], "session_id": "s1"}
        with patch("app.agents.interviewer.chief._chat_model", side_effect=RuntimeError("timeout")):
            result = await chief_think(state)

        assert route_after_chief_think(result) == "chief_execute"
        calls = result["chief_messages"][-1].tool_calls
        assert calls[0]["name"] == "design_question"
        assert calls[0]["args"] == {"focus": "new_question"}
        assert calls[0]["id"] == "fallback_design"

    @pytest.mark.asyncio
    async def test_llm_exception_on_answer_turn_falls_back_to_eval_and_design_tools(self):
        state = {
            "question_count": 1,
            "messages": [HumanMessage(content="我通过缓存把接口延迟降低了。")],
            "session_id": "s1",
        }
        with patch("app.agents.interviewer.chief._chat_model", side_effect=RuntimeError("timeout")):
            result = await chief_think(state)

        assert route_after_chief_think(result) == "chief_execute"
        calls = result["chief_messages"][-1].tool_calls
        assert [call["name"] for call in calls] == ["evaluate_answer", "design_question"]
        assert calls[1]["args"] == {"focus": "dual"}


class TestToolExceptionRecovery:
    @pytest.mark.asyncio
    async def test_evaluate_exception_writes_error_marker(self):
        state = {
            "session_id": "s1",
            "user_id": "u1",
            "target_role": "后端工程师",
            "chief_iteration": 0,
            "messages": [],
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
        with patch(
            "app.agents.interviewer.chief.run_evaluator",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM timeout"),
        ), patch(
            "app.agents.interviewer.chief.run_designer_dual",
            new_callable=AsyncMock,
            return_value={"followup_question": "追问？", "new_question": "新题？", "source": "llm"},
        ):
            result = await chief_execute(state)

        assert result["evaluator_report"]["error"] == "LLM timeout"
        assert result["evaluator_report"]["scoring"] == {}
        assert result["chief_iteration"] == 1

    @pytest.mark.asyncio
    async def test_design_exception_does_not_crash(self):
        state = {
            "session_id": "s1",
            "chief_iteration": 1,
            "messages": [],
            "chief_messages": [
                AIMessage(
                    content="",
                    tool_calls=[_tool_call("design_question", {"focus": "new_question"}, call_id="design")],
                )
            ],
        }
        with patch(
            "app.agents.interviewer.chief.run_designer",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Designer timeout"),
        ):
            result = await chief_execute(state)

        assert result["chief_iteration"] == 2
        assert result.get("designer_output") is None
        assert "Designer timeout" in result["chief_tool_results"][-1]["result"]

    @pytest.mark.asyncio
    async def test_evaluate_and_design_calls_both_agents(self):
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
        eval_mock = AsyncMock(return_value=eval_result)
        design_mock = AsyncMock(return_value=dual_result)

        with patch("app.agents.interviewer.chief._execute_evaluate", new=eval_mock), patch(
            "app.agents.interviewer.chief._execute_design_dual", new=design_mock
        ):
            result = await chief_execute(state)

        eval_mock.assert_awaited_once()
        design_mock.assert_awaited_once()
        assert result["evaluator_report"] == eval_result
        assert result["designer_dual_output"] == dual_result
        assert result.get("designer_output") is None
