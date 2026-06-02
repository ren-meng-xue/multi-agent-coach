"""验证 5 个 target_type 的 system_call adapter 接通到对应 Agent 节点。"""
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.eval.dimensions import TargetType
from app.eval.system_calls import SYSTEM_CALLS, dispatch_system_call


@pytest.mark.asyncio
async def test_question_adapter_calls_question_gen_node():
    """QUESTION → prepare.question_gen_node，返回 prepared_questions + summary。"""
    fake_out = {
        "prepared_questions": [
            {"id": 1, "question": "讲讲分布式锁", "category": "technical",
             "focus_area": "分布式", "priority": 1}
        ],
        "summary": "已定制 1 道题",
    }
    with patch(
        "app.eval.system_calls.question_gen_node",
        new=AsyncMock(return_value=fake_out),
    ) as mock_node:
        out = await dispatch_system_call(
            TargetType.QUESTION,
            {
                "direction": "Python 后端",
                "user_direction": None,
                "weak_areas": ["分布式"],
                "jd_context": None,
            },
        )

    mock_node.assert_awaited_once()
    assert isinstance(out["prepared_questions"], list)
    assert len(out["prepared_questions"]) == 1
    assert out["summary"] == "已定制 1 道题"


@pytest.mark.asyncio
async def test_scoring_adapter_converts_messages_and_returns_latest_evaluation():
    """SCORING → interviewer.evaluator_node，messages dict 转 BaseMessage，
    取 turn_evaluations 最后一条作为 evaluation。"""
    fake_eval = {
        "question_index": 0,
        "summary_score": 7.5,
        "candidate_level": "mid",
        "latent_signals": ["clear_quantification"],
        "missing_dimensions": [],
    }
    with patch(
        "app.eval.system_calls.evaluator_node",
        new=AsyncMock(return_value={
            "turn_evaluations": [fake_eval],
            "candidate_profile": {"latest_level": "mid", "latent_signals": ["clear_quantification"]},
        }),
    ) as mock_node:
        out = await dispatch_system_call(
            TargetType.SCORING,
            {
                "messages": [
                    {"role": ".ai", "content": "讲讲你的项目"},
                    {"role": "user", "content": "我做了 A/B 测试，CTR 提升 12%"},
                ],
                "target_role": "AI 工程师",
                "candidate_profile": {},
                "turn_evaluations": [],
                "question_count": 1,
                "followup_count": 0,
                "current_question_index": 0,
            },
        )

    # 验证消息已转换为 BaseMessage
    mock_node.assert_awaited_once()
    state_arg = mock_node.call_args.args[0]
    assert len(state_arg["messages"]) == 2
    assert isinstance(state_arg["messages"][0], AIMessage)
    assert isinstance(state_arg["messages"][1], HumanMessage)

    # 验证输出 shape
    assert out["evaluation"]["summary_score"] == 7.5
    assert out["evaluation"]["candidate_level"] == "mid"
    assert out["candidate_profile"]["latest_level"] == "mid"


@pytest.mark.asyncio
async def test_scoring_adapter_returns_empty_eval_when_node_yields_nothing():
    """evaluator_node 失败返回空 turn_evaluations 时，adapter 返回空 evaluation。"""
    with patch(
        "app.eval.system_calls.evaluator_node",
        new=AsyncMock(return_value={"turn_evaluations": [], "candidate_profile": {}}),
    ):
        out = await dispatch_system_call(
            TargetType.SCORING,
            {"messages": [], "target_role": "X", "candidate_profile": {}, "turn_evaluations": []},
        )

    assert out["evaluation"] == {}
    assert out["candidate_profile"] == {}


@pytest.mark.asyncio
async def test_followup_adapter_returns_assistant_message():
    """FOLLOWUP → interviewer.followup_node，返回 followup_text。"""
    with patch(
        "app.eval.system_calls.followup_node",
        new=AsyncMock(return_value={
            "assistant_message": "你刚提到 CTR 提升 12%，能讲讲你做了哪些干预实验吗？",
            "stage": "interview",
            "followup_count": 1,
        }),
    ) as mock_node:
        out = await dispatch_system_call(
            TargetType.FOLLOWUP,
            {
                "followup_focus": "quantification",
                "turn_evaluations": [{
                    "latent_signals": ["clear_quantification"],
                    "missing_dimensions": ["causal_thinking"],
                }],
                "messages": [{"role": "user", "content": "..."}],
                "target_role": "AI 工程师",
                "target_company": "Anthropic",
                "user_background": "5 年后端",
                "followup_count": 0,
            },
        )

    mock_node.assert_awaited_once()
    state_arg = mock_node.call_args.args[0]
    # 验证 messages 已转为 BaseMessage
    assert isinstance(state_arg["messages"][0], HumanMessage)
    assert out["followup_text"].startswith("你刚提到 CTR 提升")


@pytest.mark.asyncio
async def test_review_adapter_returns_review_text():
    """REVIEW → coach.review_node，返回 review_text。"""
    with patch(
        "app.eval.system_calls._coach_review_node",
        new=AsyncMock(return_value={"review_text": "你这次表现的核心问题是……"}),
    ) as mock_node:
        out = await dispatch_system_call(
            TargetType.REVIEW,
            {
                "candidate_memory": {
                    "latest_level": "junior",
                    "cumulative_signals": ["weak_quantification"],
                    "weakness_tags": [{"tag": "quantification", "count": 3}],
                    "total_sessions": 3,
                },
                "last_session_report": {"overall_score": 5.8, "improvements": ["量化不足"]},
            },
        )

    mock_node.assert_awaited_once()
    assert out["review_text"].startswith("你这次表现的核心问题")


@pytest.mark.asyncio
async def test_plan_adapter_returns_plan_json():
    """PLAN → coach.plan_node，返回 plan dict。"""
    fake_plan = {
        "summary": "本次面试在量化指标上仍有提升空间",
        "strengths": ["技术广度好"],
        "weaknesses": ["量化薄弱"],
        "next_focus_areas": ["每个项目都用数字量化产出"],
        "recommended_role": "AI 工程师",
        "recommended_question_types": ["behavioral"],
    }
    with patch(
        "app.eval.system_calls._coach_plan_node",
        new=AsyncMock(return_value={"plan_json": fake_plan}),
    ) as mock_node:
        out = await dispatch_system_call(
            TargetType.PLAN,
            {
                "review_text": "你这次表现的核心问题是量化不足",
                "candidate_memory": {"latest_level": "junior"},
            },
        )

    mock_node.assert_awaited_once()
    assert out["plan"]["summary"] == fake_plan["summary"]
    assert out["plan"]["next_focus_areas"] == fake_plan["next_focus_areas"]


@pytest.mark.asyncio
async def test_dispatch_raises_for_unknown_target_type():
    """未注册的 target_type 必须显式抛错，不允许静默返回空。"""
    with pytest.raises(ValueError, match="No system_call adapter"):
        # 故意传一个非 TargetType 的字符串绕过 dict 查找
        await dispatch_system_call("unknown_type", {})  # type: ignore[arg-type]


def test_system_calls_dict_covers_all_target_types():
    """SYSTEM_CALLS 必须覆盖全部 5 个 TargetType，防止后续新增 target_type 时漏接。"""
    expected = {
        TargetType.QUESTION,
        TargetType.SCORING,
        TargetType.FOLLOWUP,
        TargetType.REVIEW,
        TargetType.PLAN,
    }
    assert set(SYSTEM_CALLS.keys()) == expected
