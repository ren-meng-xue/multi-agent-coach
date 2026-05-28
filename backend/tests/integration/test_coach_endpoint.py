"""集成测试：验证教练复盘 API 路由挂载。"""
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth import get_current_user_id
from app.db.session import get_db
from app.main import app


@pytest.fixture
def mock_auth():
    user_id = "user_test_123"
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    yield user_id
    app.dependency_overrides.pop(get_current_user_id, None)


def test_coach_review_endpoint_access_denied(mock_auth):
    """验证教练复盘端点：无权访问时返回 403。"""
    session_id = str(uuid4())
    # Mock DB 避免异步冲突
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with TestClient(app) as client:
            resp = client.post(f"/api/v1/coach/review?session_id={session_id}")
            assert resp.status_code == 403
            data = resp.json()
            assert "无权访问" in data["msg"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_get_latest_plan_endpoint_exists(mock_auth):
    """验证获取最新计划端点已挂载。"""
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with TestClient(app) as client:
            resp = client.get("/api/v1/coach/plans/latest")
            assert resp.status_code == 200
            data = resp.json()
            # Response.ok(data=None) 返回空字典 {}
            assert data["data"] == {}
    finally:
        app.dependency_overrides.pop(get_db, None)
