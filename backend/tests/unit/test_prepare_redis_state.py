import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth import get_current_user_id
from app.main import app


async def _fake_user() -> str:
    return "user_test_redis_prepare"


@pytest.mark.asyncio
async def test_prepare_start_generates_session_id():
    app.dependency_overrides[get_current_user_id] = _fake_user
    
    mock_events = [
        {"event": "node_start", "data": {"node": "master", "label": "MASTER"}},
        {"event": "done", "data": {}}
    ]

    async def mock_stream(state):
        # 验证 state 确实包含自动生成的 session_id
        assert "session_id" in state
        assert len(state["session_id"]) > 0
        for ev in mock_events:
            yield ev

    try:
        with patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_stream):
            resp = TestClient(app).post(
                "/api/v1/prepare/start",
                data={"user_direction": "Backend Developer"},
            )
            assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_prepare_resume_pulls_from_redis():
    app.dependency_overrides[get_current_user_id] = _fake_user

    mock_redis = AsyncMock()
    # 模拟 Redis 返回上一轮的缓存状态
    cached_state = {
        "weak_areas": ["Concurrency", "SSRF"],
        "star_stories": [{"id": 1, "title": "SSRF Fix"}]
    }
    mock_redis.get.return_value = json.dumps(cached_state)

    async def mock_stream(state):
        # 验证传入 Graph 运行的 state 中正确回填了 Redis 里的缓存数据
        assert state["weak_areas"] == ["Concurrency", "SSRF"]
        assert state["star_stories"] == [{"id": 1, "title": "SSRF Fix"}]
        # 验证客户端传的 direction 有效
        assert state["user_direction"] == "Security Expert"
        yield {"event": "done", "data": {}}

    try:
        with patch("app.services.coach_opening.get_coach_redis", return_value=mock_redis), \
             patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_stream):
            
            resp = TestClient(app).post(
                "/api/v1/prepare/resume",
                data={
                    "direction": "Security Expert",
                    "session_id": "test_session_abc123"
                },
            )
            assert resp.status_code == 200
            mock_redis.get.assert_called_once_with("prepare:state:user_test_redis_prepare:test_session_abc123")
    finally:
        app.dependency_overrides.clear()
