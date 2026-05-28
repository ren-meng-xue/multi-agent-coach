"""用户面试阶段派生服务。"""
from typing import Literal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import CoachPlan, InterviewSession

UserStage = Literal["prepare", "interview", "coach"]

async def derive_user_stage(db: AsyncSession, user_id: str) -> UserStage:
    """
    根据用户最近的会话和教练计划状态，派生当前所处阶段。
    
    逻辑：
    1. 优先检查是否有进行中的 session -> interview
    2. 获取最近一场完成的 session：
       - 如果该 session 没有对应的 coach_plans -> coach
    3. 否则 -> prepare
    """
    # 1. 检查进行中的会话
    stmt_in_progress = (
        select(InterviewSession)
        .where(InterviewSession.user_id == user_id, InterviewSession.status == "in_progress")
        .limit(1)
    )
    result_in_progress = await db.execute(stmt_in_progress)
    if result_in_progress.scalar_one_or_none():
        return "interview"

    # 2. 检查最近完成的会话及复盘计划
    stmt_last_completed = (
        select(InterviewSession)
        .where(InterviewSession.user_id == user_id, InterviewSession.status == "completed")
        .order_by(desc(InterviewSession.completed_at), desc(InterviewSession.started_at))
        .limit(1)
    )
    result_last_completed = await db.execute(stmt_last_completed)
    last_session = result_last_completed.scalar_one_or_none()

    if last_session:
        # 检查该 session 是否已有 plan
        stmt_plan = (
            select(CoachPlan)
            .where(CoachPlan.session_id == last_session.id)
            .limit(1)
        )
        result_plan = await db.execute(stmt_plan)
        if not result_plan.scalar_one_or_none():
            return "coach"

    # 3. 默认阶段
    return "prepare"
