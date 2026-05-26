from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth import get_current_user_id
from app.db.session import get_db
from app.main import app


async def _fake_user() -> str:
    return "user_test_profile_no_write"


@pytest.mark.asyncio
async def test_get_profile_has_no_db_write_side_effects():
    app.dependency_overrides[get_current_user_id] = _fake_user

    # 1. 模拟 mock_db 并且监视其 commit 和 refresh
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.execute = AsyncMock()

    async def _fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _fake_get_db

    # 2. 模拟 ensure_user_exists 返回一个合法的 User
    mock_user = MagicMock()
    mock_user.id = "user_test_profile_no_write"
    mock_user.target_role = ""
    mock_user.work_years = None
    mock_user.email = "test@example.com"
    mock_user.name = "Test User"
    
    # 模拟 schema validation
    # 用 patch 拦截 ensure_user_exists
    with patch("app.api.v1.user.ensure_user_exists", return_value=mock_user):
        client = TestClient(app)
        resp = client.get("/api/v1/user/profile")
        
        assert resp.status_code == 200
        # 3. 验证 mock_db.commit 绝对没有被调用，确保无 GET 请求写副作用
        mock_db.commit.assert_not_called()
        mock_db.refresh.assert_not_called()
        
    app.dependency_overrides.clear()
