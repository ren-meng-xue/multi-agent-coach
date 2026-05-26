"""interview SSE 路由：正常流式、错误事件、鉴权与入参校验。"""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user_id
from app.db.session import get_db
from app.main import app


async def _fake_user() -> str:
    return "user_test_123"


async def _fake_db():
    yield object()


async def _fake_reply(messages, *, user_id=""):
    for t in ["你好", "，开始作答"]:
        yield t


async def _failing_reply(messages, *, user_id=""):
    raise RuntimeError("llm down")
    yield ""  # 让函数成为 async generator（unreachable）


async def _partial_then_failing_reply(messages, *, user_id=""):
    yield "先输出"
    raise RuntimeError("stream broke midway")


async def _fake_turn(message, *, user_id, db, **kwargs):
    yield {"event": "state", "data": {"stage": "opening", "question_count": 0, "total_questions": 5}}
    yield {"event": "delta", "data": {"text": "你好，先确认方向"}}
    yield {"event": "done", "data": {}}


async def _failing_turn(message, *, user_id, db, **kwargs):
    raise RuntimeError("turn down")
    yield {"event": "done", "data": {}}


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
    assert resp.headers["deprecation"] == "true"
    assert "/api/v1/interview/turn" in resp.headers["link"]


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


def test_turn_streams_without_session_id_in_request():
    """统一入口：前端只提交本轮 message，后端按登录 user_id 管内部 run。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    try:
        with patch("app.api.v1.interview.stream_interview_turn", _fake_turn):
            resp = TestClient(app).post(
                "/api/v1/interview/turn",
                json={"message": "我想练 AI Agent 工程师"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.text
    assert "event: state" in body
    assert "event: delta" in body
    assert "event: done" in body
    assert "session_id" not in body


def test_turn_emits_error_event_on_failure():
    """统一入口内部失败时仍返回 SSE error 事件。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    try:
        with patch("app.api.v1.interview.stream_interview_turn", _failing_turn):
            resp = TestClient(app).post(
                "/api/v1/interview/turn",
                json={"message": "x"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "event: error" in resp.text


def test_turn_rejects_invalid_body():
    """统一入口空 message 必须 422。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = TestClient(app).post("/api/v1/interview/turn", json={"message": "   "})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422


def test_reset_abandons_session_and_returns_ok():
    """reset 端点调用 service 层 abandon 当前 session，返回 {status: ok}。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    mock_reset = AsyncMock()
    try:
        with patch("app.api.v1.interview.reset_interview_session", mock_reset):
            resp = TestClient(app).post("/api/v1/interview/reset")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_reset.assert_awaited_once()


def test_reset_requires_auth():
    """reset 端点携带无效 token 必须 401。"""
    resp = TestClient(app).post(
        "/api/v1/interview/reset",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401


async def _fake_get_context(db, *, user_id):
    return {
        "is_returning": True,
        "target_role": "AI Agent 工程师",
        "target_company": None,
        "user_background": "LangGraph 系统",
        "session_count": 7,
    }


async def _fake_get_context_new(db, *, user_id):
    return {
        "is_returning": False,
        "target_role": None,
        "target_company": None,
        "user_background": None,
        "session_count": 0,
    }


def test_context_returns_returning_user_data():
    """GET /context 老用户：is_returning=True，含 target_role。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    try:
        with patch("app.api.v1.interview.get_user_interview_context", _fake_get_context):
            resp = TestClient(app).get("/api/v1/interview/context")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_returning"] is True
    assert body["target_role"] == "AI Agent 工程师"
    assert body["session_count"] == 7


def test_context_returns_new_user_data():
    """GET /context 新用户：is_returning=False，role 为 null。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    try:
        with patch("app.api.v1.interview.get_user_interview_context", _fake_get_context_new):
            resp = TestClient(app).get("/api/v1/interview/context")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["is_returning"] is False


def test_context_requires_auth():
    """GET /context 无效 token 必须 401。"""
    resp = TestClient(app).get(
        "/api/v1/interview/context",
        headers={"Authorization": "Bearer invalid"},
    )
    assert resp.status_code == 401


def test_reset_with_context_passes_role_to_service():
    """POST /reset 携带 target_role 时，service 以正确参数被调用。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    mock_reset = AsyncMock()
    try:
        with patch("app.api.v1.interview.reset_interview_session", mock_reset):
            resp = TestClient(app).post(
                "/api/v1/interview/reset",
                json={"target_role": "前端工程师", "user_background": "Vue 项目"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    mock_reset.assert_awaited_once()
    _, kwargs = mock_reset.call_args
    assert kwargs["target_role"] == "前端工程师"
    assert kwargs["user_background"] == "Vue 项目"


def test_reset_without_body_still_works():
    """POST /reset 不带 body 时仍然返回 {status: ok}（保持向后兼容）。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    mock_reset = AsyncMock()
    try:
        with patch("app.api.v1.interview.reset_interview_session", mock_reset):
            resp = TestClient(app).post("/api/v1/interview/reset")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_active_session_returns_data_from_service():
    """GET /active 时以正确参数调用 service 并返回有效 JSON 结构。"""
    from unittest.mock import ANY
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    mock_get_active = AsyncMock(return_value={
        "session_id": "8cf6de08-04f7-410a-b333-f725cf26d9c6",
        "target_role": "Rust 开发",
        "target_company": "字节",
        "user_background": "3年经验",
        "stage": "interview",
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "messages": [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好，请开始"}]
    })
    try:
        with patch("app.api.v1.interview.get_active_interview_session", mock_get_active):
            resp = TestClient(app).get("/api/v1/interview/active")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    mock_get_active.assert_awaited_once_with(ANY, user_id="user_test_123")
    data = resp.json()
    assert data["session_id"] == "8cf6de08-04f7-410a-b333-f725cf26d9c6"
    assert data["target_role"] == "Rust 开发"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"


def test_active_session_requires_auth():
    """GET /active 无效 token 必须 401。"""
    resp = TestClient(app).get(
        "/api/v1/interview/active",
        headers={"Authorization": "Bearer invalid"},
    )
    assert resp.status_code == 401
