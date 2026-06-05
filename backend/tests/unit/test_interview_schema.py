"""interview 请求体校验：messages 结构与边界条件。"""
import pytest
from pydantic import ValidationError

from app.schemas.interview import (
    MAX_CONTENT_LEN,
    MAX_MESSAGES,
    ChatMessage,
    ChatRequest,
    TurnRequest,
)


def test_valid_request_passes():
    """合法的 user 收尾对话应通过校验。"""
    req = ChatRequest(
        messages=[
            ChatMessage(role="user", content="想练分布式系统"),
            ChatMessage(role="assistant", content="好，第一个问题是？"),
            ChatMessage(role="user", content="开始吧"),
        ]
    )
    assert req.messages[-1].role == "user"
    assert len(req.messages) == 3


def test_empty_messages_rejected():
    """messages 不能为空。"""
    with pytest.raises(ValidationError):
        ChatRequest(messages=[])


def test_blank_content_rejected():
    """content 去空白后不能为空。"""
    with pytest.raises(ValidationError):
        ChatMessage(role="user", content="   ")


def test_content_too_long_rejected():
    """单条 content 超长应被拒绝。"""
    with pytest.raises(ValidationError):
        ChatMessage(role="user", content="x" * (MAX_CONTENT_LEN + 1))


def test_invalid_role_rejected():
    """role 只能是 user / assistant。"""
    with pytest.raises(ValidationError):
        ChatMessage(role="system", content="x")


def test_last_message_must_be_user():
    """最后一条必须是 user，否则没有可回复的输入。"""
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[
                ChatMessage(role="user", content="你好"),
                ChatMessage(role="assistant", content="你好，请问想练什么？"),
            ]
        )


def test_too_many_messages_rejected():
    """messages 条数超过上限应被拒绝，防止上下文过长。"""
    msgs = [ChatMessage(role="user", content="hi") for _ in range(MAX_MESSAGES + 1)]
    with pytest.raises(ValidationError):
        ChatRequest(messages=msgs)


def test_valid_turn_request_passes():
    """统一入口只需要本轮用户输入。"""
    req = TurnRequest(message="我想练 AI Agent 工程师面试")
    assert req.message == "我想练 AI Agent 工程师面试"


def test_blank_turn_message_allowed_for_guidance():
    """统一入口允许空白 message，由 SSE 路由返回礼貌引导而非 422。"""
    req = TurnRequest(message="   ")
    assert req.message == ""


def test_turn_message_too_long_rejected():
    """统一入口单轮 message 也要限制长度。"""
    with pytest.raises(ValidationError):
        TurnRequest(message="x" * (MAX_CONTENT_LEN + 1))


def test_user_context_response_new_user():
    """新用户：is_returning=False，role/company/background 均为 None，session_count=0。"""
    from app.schemas.interview import UserContextResponse

    resp = UserContextResponse(
        is_returning=False,
        target_role=None,
        target_company=None,
        user_background=None,
        session_count=0,
    )
    assert resp.is_returning is False
    assert resp.session_count == 0


def test_user_context_response_returning_user():
    """老用户：is_returning=True，role 有值。"""
    from app.schemas.interview import UserContextResponse

    resp = UserContextResponse(
        is_returning=True,
        target_role="AI Agent 工程师",
        target_company="字节跳动",
        user_background="LangGraph 系统",
        session_count=7,
    )
    assert resp.is_returning is True
    assert resp.target_role == "AI Agent 工程师"


def test_reset_request_allows_empty_body():
    """ResetRequest 的两个字段均为可选，空 body 等价于 {}。"""
    from app.schemas.interview import ResetRequest

    req = ResetRequest()
    assert req.target_role is None
    assert req.user_background is None


def test_reset_request_with_context():
    """ResetRequest 可携带岗位与背景。"""
    from app.schemas.interview import ResetRequest

    req = ResetRequest(target_role="前端工程师", user_background="Vue 项目")
    assert req.target_role == "前端工程师"


def test_coach_opening_message_response_shape():
    """Coach 开场词响应必须是前端可直接渲染的展示文案。"""
    from app.schemas.interview import CoachOpeningMessageResponse

    resp = CoachOpeningMessageResponse(
        greeting="欢迎回来",
        weakness_summary="你的项目表达缺少量化结果，面试官很难判断真实贡献。",
        evidence="这个短板在你过去 7 场面试中出现了 5 场。",
        focus_today="今天重点练量化表达。",
        cta_type="returning",
    )

    assert resp.weakness_summary == "你的项目表达缺少量化结果，面试官很难判断真实贡献。"
    assert resp.evidence == "这个短板在你过去 7 场面试中出现了 5 场。"
    assert resp.cta_type == "returning"
