"""interview SSE 路由：正常流式、错误事件、鉴权与入参校验。"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user_id
from app.main import app


async def _fake_user() -> str:
    return "user_test_123"


async def _fake_reply(messages, *, user_id=""):
    for t in ["你好", "，开始作答"]:
        yield t


async def _failing_reply(messages, *, user_id=""):
    raise RuntimeError("llm down")
    yield ""  # 让函数成为 async generator（unreachable）


async def _partial_then_failing_reply(messages, *, user_id=""):
    yield "先输出"
    raise RuntimeError("stream broke midway")


def test_chat_streams_delta_and_done():
    """正常路径：返回 SSE，含 delta 事件与结束的 done 事件。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    try:
        with patch("app.api.v1.interview.stream_interview_reply", _fake_reply):
            resp = TestClient(app).post(
                "/api/v1/interview/chat",
                json={"messages": [{"role": "user", "content": "想练分布式"}]},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.text
    assert "event: delta" in body
    assert "你好" in body
    assert "event: done" in body


def test_chat_emits_error_event_on_failure():
    """LLM 失败：以 error 事件返回，而非抛 500。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    try:
        with patch("app.api.v1.interview.stream_interview_reply", _failing_reply):
            resp = TestClient(app).post(
                "/api/v1/interview/chat",
                json={"messages": [{"role": "user", "content": "x"}]},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "event: error" in resp.text


def test_chat_emits_error_event_after_partial_output():
    """LLM 中途断流：保留已发 delta，并继续用 error 事件告知前端。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    try:
        with patch("app.api.v1.interview.stream_interview_reply", _partial_then_failing_reply):
            resp = TestClient(app).post(
                "/api/v1/interview/chat",
                json={"messages": [{"role": "user", "content": "x"}]},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "event: delta" in resp.text
    assert "先输出" in resp.text
    assert "event: error" in resp.text


def test_chat_requires_auth():
    """无有效 token 必须 401。"""
    resp = TestClient(app).post(
        "/api/v1/interview/chat",
        json={"messages": [{"role": "user", "content": "x"}]},
        headers={"Authorization": "Bearer invalid"},
    )
    assert resp.status_code == 401


def test_chat_rejects_invalid_body():
    """空 messages 必须 422。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    try:
        resp = TestClient(app).post("/api/v1/interview/chat", json={"messages": []})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422
