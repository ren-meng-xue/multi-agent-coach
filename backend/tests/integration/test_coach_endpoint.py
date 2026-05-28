"""集成测试：验证教练复盘 API 路由挂载。"""
import pytest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.auth import get_current_user_id

@pytest.fixture
def mock_auth():
    user_id = "user_test_123"
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    yield user_id
    app.dependency_overrides.pop(get_current_user_id, None)

def test_coach_review_endpoint_access_denied(mock_auth):
    """验证教练复盘端点：无权访问时返回 403。"""
    session_id = str(uuid4())
    # 模拟 DB 查询返回 None，触发 403
    with patch("app.api.v1.coach.get_db", return_value=None):
        with TestClient(app) as client:
            resp = client.post(f"/api/v1/coach/review?session_id={session_id}")
            assert resp.status_code == 403
            data = resp.json()
            assert "无权访问" in data["msg"]

def test_get_latest_plan_endpoint_exists(mock_auth):
    """验证获取最新计划端点已挂载。"""
    # 只要不抛 404 就说明挂载成功
    with patch("app.api.v1.coach.get_db", return_value=None):
        with TestClient(app) as client:
            resp = client.get("/api/v1/coach/plans/latest")
            # 注意：此处可能会因为权限检查或 DB mock 不全返回非 200，但只要不是 404 即可
            assert resp.status_code != 404
