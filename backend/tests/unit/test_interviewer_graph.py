"""面试官 LangGraph：阶段路由、追问和结束分支。"""
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.interviewer import graph as graph_module
from app.agents.interviewer.graph import run_interviewer_turn
from app.agents.interviewer.nodes import BriefingIntentOutput, DecideNextOutput, OpeningInfoOutput


async def test_new_session_returns_opening(monkeypatch):
    """新 run 首轮进入 opening，先收集方向信息。"""

    async def fake_opening(state):
        return "你在准备什么方向的面试？"

    async def fake_extract(state):
        return OpeningInfoOutput(
            complete=False,
            missing_fields=["target_role", "target_company", "user_background"],
        )

    monkeypatch.setattr("app.agents.interviewer.nodes.extract_opening_info", fake_extract)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_opening_reply", fake_opening)

    out = await run_interviewer_turn(
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "is_first_time": True,
            "messages": [HumanMessage(content="开始")],
            "stage": "opening",
            "question_count": 0,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "opening"
    assert out["assistant_message"] == "你在准备什么方向的面试？"


async def test_opening_reply_then_asks_first_question(monkeypatch):
    """opening 已问过后，用户补充方向信息，进入 briefing，确认后进入第一题。"""

    async def fake_extract(state):
        return OpeningInfoOutput(
            complete=True,
            target_role="AI Agent 工程师",
            target_company="大厂",
            user_background="多 Agent 面试教练项目",
        )

    async def fake_briefing(state):
        return "好的！本次面试共 5 道题，结束后会生成报告。准备好了吗？"

    async def fake_detect(state):
        return BriefingIntentOutput(intent="continue")

    async def fake_question(state):
        return "第一题，请介绍你做过的 LangGraph 项目。"

    monkeypatch.setattr("app.agents.interviewer.nodes.extract_opening_info", fake_extract)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_briefing_reply", fake_briefing)
    monkeypatch.setattr("app.agents.interviewer.nodes.detect_briefing_intent", fake_detect)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_question_reply", fake_question)

    out = await run_interviewer_turn(
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "is_first_time": True,
            "messages": [
                AIMessage(content="你在准备什么方向的面试？"),
                HumanMessage(content="AI Agent 工程师，想练项目经历"),
            ],
            "stage": "opening",
            "question_count": 0,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "briefing"
    assert out["target_role"] == "AI Agent 工程师"
    assert out["target_company"] == "大厂"
    assert out["user_background"] == "多 Agent 面试教练项目"
    assert out["assistant_message"] == "好的！本次面试共 5 道题，结束后会生成报告。准备好了吗？"

    # 模拟第二轮：用户说准备好了，开始面试，进入第一题
    out["messages"].append(AIMessage(content=out["assistant_message"]))
    out["messages"].append(HumanMessage(content="准备好了，开始吧"))

    out2 = await run_interviewer_turn(out)

    assert out2["stage"] == "interview"
    assert out2["question_count"] == 1
    assert out2["assistant_message"] == "第一题，请介绍你做过的 LangGraph 项目。"



async def test_interview_answer_can_route_to_followup(monkeypatch):
    """回答质量不足且未超过追问上限时，进入追问节点。"""

    async def fake_decide(state):
        return DecideNextOutput(
            action="followup",
            reason="缺少量化结果",
            followup_question="你能补充具体指标吗？",
            depth_analysis="尚未覆盖量化指标",
        )

    monkeypatch.setattr("app.agents.interviewer.nodes.decide_next_action", fake_decide)

    out = await run_interviewer_turn(
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "is_first_time": False,
            "messages": [HumanMessage(content="我优化了很多。")],
            "stage": "interview",
            "question_count": 1,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "interview"
    assert out["followup_count"] == 1
    assert out["assistant_message"] == "你能补充具体指标吗？"


async def test_fifth_answer_routes_to_closing(monkeypatch):
    """第 5 题回答后优先结束，不再继续追问。"""

    async def fake_closing(state):
        return "本次模拟面试结束。"

    monkeypatch.setattr("app.agents.interviewer.nodes.generate_closing_reply", fake_closing)

    out = await run_interviewer_turn(
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "is_first_time": False,
            "messages": [HumanMessage(content="第五题回答")],
            "stage": "interview",
            "question_count": 5,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "closing"
    assert out["assistant_message"] == "本次模拟面试结束。"


async def test_followup_limit_reached_routes_to_next_question(monkeypatch):
    """追问次数耗尽时，decide_next 硬判断跳过 LLM 直接进入下一题，followup_count 重置为 0。"""

    async def fake_question(state):
        return "第二题，请描述你的架构设计思路。"

    monkeypatch.setattr("app.agents.interviewer.nodes.generate_question_reply", fake_question)

    out = await run_interviewer_turn(
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "is_first_time": False,
            "messages": [HumanMessage(content="用了缓存。")],
            "stage": "interview",
            "question_count": 1,
            "total_questions": 5,
            "followup_count": 2,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "interview"
    assert out["question_count"] == 2
    assert out["followup_count"] == 0
    assert out["assistant_message"] == "第二题，请描述你的架构设计思路。"


async def test_stream_interviewer_turn_events_only_yields_tagged_answer_tokens(monkeypatch):
    """LangGraph token 流只下发回答节点 token，并保留最终 state。"""

    class FakeGraph:
        async def astream_events(self, state, config, version):
            yield {
                "event": "on_chat_model_stream",
                "tags": ["structured_output"],
                "data": {"chunk": SimpleNamespace(content='{"action"')},
            }
            yield {
                "event": "on_chat_model_stream",
                "tags": ["interviewer_answer_stream"],
                "data": {"chunk": SimpleNamespace(content="第一题")},
            }
            yield {
                "event": "on_chat_model_stream",
                "tags": ["interviewer_answer_stream"],
                "data": {"chunk": SimpleNamespace(content="，请回答")},
            }
            yield {
                "event": "on_chain_end",
                "name": "LangGraph",
                "data": {"output": {**state, "assistant_message": "第一题，请回答"}},
            }

    monkeypatch.setattr(graph_module, "get_interviewer_graph", lambda: FakeGraph())

    events = [
        event
        async for event in graph_module.stream_interviewer_turn_events(
            {
                "session_id": "session-stream",
                "user_id": "user-1",
                "is_first_time": False,
                "messages": [HumanMessage(content="开始")],
                "stage": "interview",
                "question_count": 0,
                "total_questions": 5,
                "followup_count": 0,
                "max_followups": 2,
            }
        )
    ]

    assert [event["event"] for event in events] == ["token", "token", "final"]
    assert [event["data"]["text"] for event in events[:2]] == ["第一题", "，请回答"]


async def test_report_node_returns_structured_report(monkeypatch):
    """report_node 在完整对话后返回含所有字段的结构化评分。"""
    from app.agents.interviewer.nodes import ReportOutput, report_node

    async def fake_generate_report(state):
        return ReportOutput(
            overall_score=7.5,
            technical_depth=4.0,
            quantified_results=3.0,
            failure_tradeoffs=4.0,
            structure=3.5,
            highlights=["设计清晰", "表达有条理"],
            improvements=["缺少量化数据", "可补充失败案例"],
            key_concepts=["分布式系统"],
            common_mistakes=["缺少量化"],
        )

    monkeypatch.setattr("app.agents.interviewer.nodes.generate_report_output", fake_generate_report)

    state = {
        "session_id": "s1",
        "user_id": "u1",
        "is_first_time": False,
        "messages": [HumanMessage(content="用了缓存方案"), AIMessage(content="不错")],
        "stage": "closing",
        "question_count": 5,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }

    result = await report_node(state)

    assert result["report"]["overall_score"] == 7.5
    assert result["report"]["technical_depth"] == 4.0
    assert result["report"]["highlights"] == ["设计清晰", "表达有条理"]
    assert result["report"]["improvements"] == ["缺少量化数据", "可补充失败案例"]


async def test_report_node_returns_empty_dict_on_unexpected_output(monkeypatch):
    """generate_report_output 返回 None 时，report_node 返回空 dict 并记录 warning。"""
    from app.agents.interviewer.nodes import report_node

    async def fake_generate_report(state):
        return None

    monkeypatch.setattr("app.agents.interviewer.nodes.generate_report_output", fake_generate_report)

    state = {
        "session_id": "s2",
        "user_id": "u1",
        "is_first_time": False,
        "messages": [HumanMessage(content="回答")],
        "stage": "closing",
        "question_count": 5,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }

    result = await report_node(state)
    assert result["report"] == {}


async def test_new_session_with_null_stage_routes_to_opening(monkeypatch):
    """新 session stage=None（SQLAlchemy server_default 未回填）时应路由到 opening，而非直接出题。"""

    async def fake_opening(state):
        return "你在准备什么方向的面试？"

    async def fake_extract(state):
        return OpeningInfoOutput(
            complete=False,
            missing_fields=["target_role", "target_company", "user_background"],
        )

    monkeypatch.setattr("app.agents.interviewer.nodes.extract_opening_info", fake_extract)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_opening_reply", fake_opening)

    out = await run_interviewer_turn(
        {
            "session_id": "session-null-stage",
            "user_id": "user-1",
            "is_first_time": True,
            "messages": [HumanMessage(content="AI Agent 工程师")],
            "stage": None,  # 模拟 SQLAlchemy flush 后 server_default 未回填的情况
            "question_count": 0,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "opening"
    assert out["assistant_message"] == "你在准备什么方向的面试？"


async def test_opening_complete_shows_briefing_not_question(monkeypatch):
    """opening 信息收集完成后，先展示 briefing 消息，不直接出题。"""

    async def fake_extract(state):
        return OpeningInfoOutput(
            complete=True,
            target_role="AI Agent 工程师",
            target_company="",
            user_background="",
        )

    async def fake_briefing(state):
        return "好的！本次面试共 5 道题，结束后会生成报告。准备好了吗？"

    monkeypatch.setattr("app.agents.interviewer.nodes.extract_opening_info", fake_extract)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_briefing_reply", fake_briefing)

    out = await run_interviewer_turn(
        {
            "session_id": "session-briefing-1",
            "user_id": "user-1",
            "is_first_time": True,
            "messages": [HumanMessage(content="AI Agent 工程师")],
            "stage": "opening",
            "question_count": 0,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "briefing"
    assert out["target_role"] == "AI Agent 工程师"
    assert out["assistant_message"] == "好的！本次面试共 5 道题，结束后会生成报告。准备好了吗？"


async def test_briefing_continue_routes_to_first_question(monkeypatch):
    """briefing 阶段用户表示准备好，进入第一道正式题。"""

    async def fake_detect(state):
        return BriefingIntentOutput(intent="continue")

    async def fake_question(state):
        return "第一题：请介绍你做过的 AI Agent 项目。"

    monkeypatch.setattr("app.agents.interviewer.nodes.detect_briefing_intent", fake_detect)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_question_reply", fake_question)

    out = await run_interviewer_turn(
        {
            "session_id": "session-briefing-2",
            "user_id": "user-1",
            "is_first_time": True,
            "messages": [
                AIMessage(content="准备好了吗？"),
                HumanMessage(content="好的，开始吧"),
            ],
            "stage": "briefing",
            "target_role": "AI Agent 工程师",
            "question_count": 0,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "interview"
    assert out["question_count"] == 1
    assert out["assistant_message"] == "第一题：请介绍你做过的 AI Agent 项目。"


async def test_briefing_change_info_routes_back_to_opening(monkeypatch):
    """briefing 阶段用户想换方向，回到 opening 重新收集信息。"""

    async def fake_detect(state):
        return BriefingIntentOutput(intent="change_info")

    async def fake_extract(state):
        return OpeningInfoOutput(complete=False, missing_fields=["target_role"])

    async def fake_opening(state):
        return "当然！请告诉我你想换成哪个方向？"

    monkeypatch.setattr("app.agents.interviewer.nodes.detect_briefing_intent", fake_detect)
    monkeypatch.setattr("app.agents.interviewer.nodes.extract_opening_info", fake_extract)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_opening_reply", fake_opening)

    out = await run_interviewer_turn(
        {
            "session_id": "session-briefing-3",
            "user_id": "user-1",
            "is_first_time": True,
            "messages": [
                AIMessage(content="准备好了吗？"),
                HumanMessage(content="我想换个方向，练后端工程师"),
            ],
            "stage": "briefing",
            "target_role": "AI Agent 工程师",
            "question_count": 0,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "opening"
    assert out["assistant_message"] == "当然！请告诉我你想换成哪个方向？"


async def test_briefing_not_ready_stays_in_briefing(monkeypatch):
    """briefing 阶段用户说还没准备好，停留在 briefing 并给出等待回复。"""

    async def fake_detect(state):
        return BriefingIntentOutput(intent="not_ready")

    async def fake_not_ready(state):
        return "没关系，准备好了随时告诉我！"

    monkeypatch.setattr("app.agents.interviewer.nodes.detect_briefing_intent", fake_detect)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_not_ready_reply", fake_not_ready)

    out = await run_interviewer_turn(
        {
            "session_id": "session-briefing-4",
            "user_id": "user-1",
            "is_first_time": True,
            "messages": [
                AIMessage(content="准备好了吗？"),
                HumanMessage(content="等一下，还没准备好"),
            ],
            "stage": "briefing",
            "target_role": "AI Agent 工程师",
            "question_count": 0,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "briefing"
    assert out["assistant_message"] == "没关系，准备好了随时告诉我！"


async def test_llm_closing_decision_ignored_when_questions_remain(monkeypatch):
    """LLM 错误地决定 closing 时，若题目未完成，路由层应忽略该决定并继续出题。"""

    async def fake_decide(state):
        return DecideNextOutput(action="closing", reason="感觉回答完了", depth_analysis="话题已充分覆盖")

    async def fake_question(state):
        return "第二题：请描述你遇到的最大技术挑战。"

    monkeypatch.setattr("app.agents.interviewer.nodes.decide_next_action", fake_decide)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_question_reply", fake_question)

    out = await run_interviewer_turn(
        {
            "session_id": "session-premature-close",
            "user_id": "user-1",
            "is_first_time": False,
            "messages": [HumanMessage(content="我做过一个 RAG 系统。")],
            "stage": "interview",
            "question_count": 1,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "interview"
    assert out["question_count"] == 2
    assert out["assistant_message"] == "第二题：请描述你遇到的最大技术挑战。"


async def test_closing_turn_returns_report_in_state(monkeypatch):
    """closing 阶段完成后，图输出 state 中包含 report 字段。"""
    from app.agents.interviewer.nodes import ReportOutput

    async def fake_closing(state):
        return "本次模拟面试结束，感谢参与。"

    async def fake_generate_report(state):
        return ReportOutput(
            overall_score=8.0,
            technical_depth=4.0,
            quantified_results=4.0,
            failure_tradeoffs=4.0,
            structure=4.0,
            highlights=["整体表现良好"],
            improvements=["可补充更多细节"],
            key_concepts=["系统设计"],
            common_mistakes=["缺少量化"],
        )

    monkeypatch.setattr("app.agents.interviewer.nodes.generate_closing_reply", fake_closing)
    monkeypatch.setattr("app.agents.interviewer.nodes.generate_report_output", fake_generate_report)

    out = await run_interviewer_turn(
        {
            "session_id": "session-report-1",
            "user_id": "user-1",
            "is_first_time": False,
            "messages": [HumanMessage(content="第五题回答内容详细。")],
            "stage": "interview",
            "question_count": 5,
            "total_questions": 5,
            "followup_count": 0,
            "max_followups": 2,
        }
    )

    assert out["stage"] == "closing"
    assert out["assistant_message"] == "本次模拟面试结束，感谢参与。"
    assert "report" in out
    assert out["report"]["overall_score"] == 8.0
    assert out["report"]["highlights"] == ["整体表现良好"]
