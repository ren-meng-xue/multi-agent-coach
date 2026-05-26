"""面试历史记录服务。"""
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import InterviewSession
from app.schemas.interview import InterviewHistoryItem, InterviewHistoryResponse


async def get_interview_history(
    db: AsyncSession, *, user_id: str, limit: int = 10
) -> InterviewHistoryResponse:
    """返回用户的面试历史记录，按开始时间倒序排列。"""
    result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "completed",
            InterviewSession.score.isnot(None),
        )
        .order_by(InterviewSession.started_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        items.append(
            InterviewHistoryItem(
                id=s.id,
                # 简单格式化日期，前端也可以自行处理
                date=s.started_at.strftime("%m月%d日") if s.started_at else "",
                topic=s.target_role or "模拟面试",
                target_role=s.target_role or "",
                score=float(s.score) if s.score is not None else 0.0,
                pass_fail=cast(
                    Literal["pass", "fail", "partial"],
                    s.pass_fail if s.pass_fail in ("pass", "fail", "partial") else "fail"
                ),
                key_issues=s.key_issues if isinstance(s.key_issues, list) else [],
                report=s.report_json,
            )
        )

    return InterviewHistoryResponse(sessions=items)
