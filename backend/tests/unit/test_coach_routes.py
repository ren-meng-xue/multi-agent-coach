"""Coach 路由：个性化开场词接口。"""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user_id
from app.db.session import get_db
from app.main import app
from app.schemas.interview import CoachOpeningMessageResponse


async def _fake_user() -> str:
    return "user_test_123"


async def _fake_db():
    yield object()


def test_opening_message_returns_structured_json():
    """GET /api/coach/opening-message 返回 LLM 生成的结构化开场词。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    payload = CoachOpeningMessageResponse(
        greeting="欢迎回来，今天继续练 AI Agent 面试。",
        weakness_summary="你在结果量化方面不足，项目收益说得不够具体。",
        evidence="这个短板在你过去 7 场面试中出现了 5 场。",
        focus_today="今天重点练习用数据证明项目收益。",
        cta_type="returning",
    )
    mock_generate = AsyncMock(return_value=payload)

    try:
        with patch("app.api.coach.generate_coach_opening_message", mock_generate):
            resp = TestClient(app).get("/api/coach/opening-message")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["greeting"] == "欢迎回来，今天继续练 AI Agent 面试。"
    assert body["weakness_summary"] == "你在结果量化方面不足，项目收益说得不够具体。"
    assert body["evidence"] == "这个短板在你过去 7 场面试中出现了 5 场。"
    assert body["cta_type"] == "returning"
    mock_generate.assert_awaited_once()


def test_opening_message_requires_auth():
    """无有效 token 必须 401。"""
    resp = TestClient(app).get(
        "/api/coach/opening-message",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401
