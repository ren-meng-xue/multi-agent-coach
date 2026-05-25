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


def test_blank_turn_message_rejected():
    """统一入口 message 不能为空。"""
    with pytest.raises(ValidationError):
        TurnRequest(message="   ")


def test_turn_message_too_long_rejected():
    """统一入口单轮 message 也要限制长度。"""
    with pytest.raises(ValidationError):
        TurnRequest(message="x" * (MAX_CONTENT_LEN + 1))
