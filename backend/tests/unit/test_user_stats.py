"""测试用户看板统计服务。"""
from datetime import UTC, datetime, timedelta

import pytest

from app.models.core import InterviewSession, User
from app.services.user_stats import get_user_dashboard_data


@pytest.mark.asyncio
async def test_dashboard_duration_sums_completed_session_intervals(db):
    """累计练习时长按真正完成面试的开始到结束间隔累加。"""
    user = User(id="user_dashboard_duration", email="dashboard-duration@example.com")
    base_time = datetime(2026, 6, 2, 8, 0, tzinfo=UTC)
    completed_with_score = InterviewSession(
        user_id=user.id,
        status="completed",
        started_at=base_time,
        completed_at=base_time + timedelta(minutes=30),
        score=8.0,
        report_json={
            "technical_depth": 8,
            "quantified_results": 7,
            "failure_tradeoffs": 6,
            "structure": 9,
        },
    )
    completed_without_score = InterviewSession(
        user_id=user.id,
        status="completed",
        started_at=base_time + timedelta(hours=1),
        completed_at=base_time + timedelta(hours=2, minutes=30),
    )
    incomplete = InterviewSession(
        user_id=user.id,
        status="in_progress",
        started_at=base_time,
        completed_at=None,
    )
    abandoned = InterviewSession(
        user_id=user.id,
        status="abandoned",
        started_at=base_time,
        completed_at=base_time + timedelta(hours=5),
    )
    db.add_all([user, completed_with_score, completed_without_score, incomplete, abandoned])
    await db.flush()

    dashboard = await get_user_dashboard_data(db, user_id=user.id)

    assert dashboard.session_count == 2
    assert dashboard.total_duration_hours == 2.0
    assert dashboard.average_score == 8.0
    assert [point.session_index for point in dashboard.growth_trajectory] == [1]
