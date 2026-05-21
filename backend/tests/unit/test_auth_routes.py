"""验证认证 API：后端能基于 Clerk user id 暴露当前登录用户。"""

from fastapi.testclient import TestClient

from app.core.auth import get_current_user_id
from app.main import app


async def _fake_current_user_id() -> str:
    """测试替身：跳过 JWT 解码，模拟已通过 Clerk 鉴权的用户。"""
    return "user_test_123"


def test_auth_me_returns_current_clerk_user_id():
    """GET /api/v1/auth/me 必须返回当前 Clerk 用户 id。"""
    app.dependency_overrides[get_current_user_id] = _fake_current_user_id
    try:
        response = TestClient(app).get("/api/v1/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"] == {"user_id": "user_test_123"}
