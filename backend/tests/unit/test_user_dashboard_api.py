"""测试用户看板数据 API。"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.core.auth import get_current_user_id
from app.db.session import get_db
from app.main import app
from app.schemas.user import DashboardData, RadarData, GrowthPoint, WeaknessTag


async def _fake_user() -> str:
    return "user_test_dashboard"


async def _fake_db():
    yield AsyncMock()


def test_get_dashboard_success():
    """测试获取看板数据成功路径。"""
    mock_data = DashboardData(
        session_count=10,
        total_duration_hours=5.5,
        average_score=8.2,
        weaknesses_improved_count=3,
        radar=RadarData(
            technical_depth=8.0,
            quantified_results=7.5,
            failure_tradeoffs=8.5,
            structure=9.0
        ),
        growth_trajectory=[
            GrowthPoint(session_index=1, score=7.0),
            GrowthPoint(session_index=2, score=8.2)
        ],
        weaknesses=[
            WeaknessTag(tag="高并发", severity="severe"),
            WeaknessTag(tag="STAR 完整性", severity="warn")
        ]
    )

    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    
    try:
        with patch("app.api.v1.user.get_user_dashboard_data", AsyncMock(return_value=mock_data)):
            resp = TestClient(app).get("/api/v1/user/dashboard")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["code"] == 200
    assert json_data["msg"] == "success"
    data = json_data["data"]
    assert data["session_count"] == 10
    assert data["average_score"] == 8.2
    assert data["radar"]["technical_depth"] == 8.0
    assert len(data["growth_trajectory"]) == 2
    assert data["weaknesses"][0]["tag"] == "高并发"
