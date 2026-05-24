"""interview_chat service：OpenAI 流式封装的正常、重试、超时、中途异常路径。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APITimeoutError
from tenacity import wait_none

from app.schemas.interview import ChatMessage
from app.services.interview_chat import stream_interview_reply


@pytest.fixture(autouse=True)
def _no_retry_wait():
    """关掉重试等待，避免测试真实 sleep（不稳定时间依赖）。"""
    from app.services import interview_chat

    original = interview_chat._create_stream.retry.wait
    interview_chat._create_stream.retry.wait = wait_none()
    yield
    interview_chat._create_stream.retry.wait = original


def _chunk(content: str | None):
    """构造与 OpenAI ChatCompletionChunk 同形的最小对象。"""
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


def _empty_choices_chunk():
    """模拟 provider 发送不含 choices 的流式尾包。"""
    return SimpleNamespace(choices=[])


async def _fake_stream(contents, fail_at=None):
    """模拟 OpenAI 流：逐 chunk 产出，fail_at 处抛错模拟中途断流。"""
    for i, c in enumerate(contents):
        if fail_at is not None and i == fail_at:
            raise RuntimeError("stream broke midway")
        yield c if hasattr(c, "choices") else _chunk(c)


def _client_returning(stream):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=stream)
    return client


def _client_raising(exc):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=exc)
    return client


async def test_streams_text_chunks():
    """正常路径：逐 chunk 拼出完整回复，跳过空 delta。"""
    client = _client_returning(_fake_stream(["你好", None, "，请", "作答"]))
    with patch("app.services.interview_chat._get_client", return_value=client):
        out = [t async for t in stream_interview_reply([ChatMessage(role="user", content="hi")])]
    assert "".join(out) == "你好，请作答"


async def test_skips_empty_choices_chunks():
    """兼容 provider 发出的无 choices 流式包，避免 IndexError 中断 SSE。"""
    client = _client_returning(_fake_stream(["你好", _empty_choices_chunk(), "，请作答"]))
    with patch("app.services.interview_chat._get_client", return_value=client):
        out = [t async for t in stream_interview_reply([ChatMessage(role="user", content="hi")])]
    assert "".join(out) == "你好，请作答"


async def test_create_failure_retries_three_times_then_raises():
    """建流阶段超时：重试 3 次后仍失败则抛出（覆盖 retry + timeout 路径）。"""
    client = _client_raising(APITimeoutError(request=httpx.Request("POST", "http://test")))
    with (
        patch("app.services.interview_chat._get_client", return_value=client),
        pytest.raises(APITimeoutError),
    ):
        [t async for t in stream_interview_reply([ChatMessage(role="user", content="hi")])]
    assert client.chat.completions.create.call_count == 3


async def test_midstream_error_propagates_after_partial_output():
    """迭代中断流：已产出的内容保留，之后异常向上抛（迭代阶段不重试）。"""
    client = _client_returning(_fake_stream(["你", "好"], fail_at=1))
    collected = []
    with (
        patch("app.services.interview_chat._get_client", return_value=client),
        pytest.raises(RuntimeError),
    ):
        async for t in stream_interview_reply([ChatMessage(role="user", content="hi")]):
            collected.append(t)
    assert collected == ["你"]
    # 中途异常只调用一次 create，绝不重试（否则会重复输出）
    assert client.chat.completions.create.call_count == 1
