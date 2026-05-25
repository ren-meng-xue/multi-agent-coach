# backend/tests/integration/test_prepare_api.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.v1.auth import get_current_user_id
from app.main import app


async def _fake_user() -> str:
    return "user_test_123"


def test_prepare_start_returns_sse_stream():
    """POST /api/v1/prepare/start 应返回 SSE 流。"""
    app.dependency_overrides[get_current_user_id] = _fake_user

    mock_events = [
        {"event": "node_start", "data": {"node": "master", "label": "MASTER"}},
        {
            "event": "node_done",
            "data": {
                "node": "master",
                "elapsed_ms": 10,
                "chain": ["question_gen"],
                "need_direction": False,
            },
        },
        {
            "event": "done",
            "data": {
                "prepared_questions": [],
                "summary": "测试摘要",
                "direction": "AI Agent",
            },
        },
    ]

    async def mock_stream(state):
        for ev in mock_events:
            yield ev

    try:
        with patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_stream):
            resp = TestClient(app).post(
                "/api/v1/prepare/start",
                data={"user_direction": "AI Agent 工程师"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "node_start" in resp.text
    assert "测试摘要" in resp.text
