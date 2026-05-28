"""验证用户阶段派生逻辑。"""
import pytest
from datetime import datetime
from app.models.core import User, InterviewSession, CoachPlan
from app.services.user_stage import derive_user_stage

@pytest.fixture
async def test_user(db):
    user_id = f"user_stage_{datetime.now().timestamp()}"
    user = User(id=user_id, email=f"stage_{user_id}@example.com")
    db.add(user)
    await db.commit()
    return user

@pytest.mark.asyncio
async def test_stage_prepare_when_no_sessions(db, test_user):
    """无 session 时应为 prepare 阶段。"""
    assert await derive_user_stage(db, test_user.id) == "prepare"

@pytest.mark.asyncio
async def test_stage_interview_when_in_progress(db, test_user):
    """有进行中 session 时应为 interview 阶段。"""
    session = InterviewSession(user_id=test_user.id, status="in_progress")
    db.add(session)
    await db.commit()
    assert await derive_user_stage(db, test_user.id) == "interview"

@pytest.mark.asyncio
async def test_stage_coach_when_completed_no_plan(db, test_user):
    """最近面试已完成但无 plan 时应为 coach 阶段。"""
    session = InterviewSession(user_id=test_user.id, status="completed")
    db.add(session)
    await db.commit()
    assert await derive_user_stage(db, test_user.id) == "coach"

@pytest.mark.asyncio
async def test_stage_prepare_when_completed_with_plan(db, test_user):
    """最近面试已完成且已有 plan 时应回退到 prepare 阶段。"""
    session = InterviewSession(user_id=test_user.id, status="completed")
    db.add(session)
    await db.flush()
    
    plan = CoachPlan(user_id=test_user.id, session_id=session.id, plan_json={"summary": "test"})
    db.add(plan)
    await db.commit()
    
    assert await derive_user_stage(db, test_user.id) == "prepare"
