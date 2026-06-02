"""验证用户阶段 API 接口。"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user_id
from app.main import app


@pytest.fixture
def mock_auth():
    """Mock 认证，返回测试用户 ID。"""
    app.dependency_overrides[get_current_user_id] = lambda: "user_stage_api_test"
    yield
    app.dependency_overrides.pop(get_current_user_id, None)

def test_get_user_stage_api_prepare(mock_auth):
    """测试获取用户阶段：prepare。"""
    with patch("app.api.v1.user.derive_user_stage", new_callable=AsyncMock) as mock_derive:
        mock_derive.return_value = "prepare"
        with TestClient(app) as client:
            resp = client.get("/api/v1/user/stage")
            assert resp.status_code == 200
            data = resp.json()
            assert data["code"] == 200
            assert data["data"]["stage"] == "prepare"

def test_get_user_stage_api_interview(mock_auth):
    """测试获取用户阶段：interview。"""
    with patch("app.api.v1.user.derive_user_stage", new_callable=AsyncMock) as mock_derive:
        mock_derive.return_value = "interview"
        with TestClient(app) as client:
            resp = client.get("/api/v1/user/stage")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["stage"] == "interview"

def test_get_user_stage_api_coach(mock_auth):
    """测试获取用户阶段：coach。"""
    with patch("app.api.v1.user.derive_user_stage", new_callable=AsyncMock) as mock_derive:
        mock_derive.return_value = "coach"
        with TestClient(app) as client:
            resp = client.get("/api/v1/user/stage")
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["stage"] == "coach"
