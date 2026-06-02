"""教练复盘 API 路由。"""
import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents.coach.graph import stream_coach_full_events
from app.api.v1.auth import get_current_user_id
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.core import CoachPlan, InterviewSession
from app.schemas.coach import CoachPlanResponse
from app.schemas.interview import CoachOpeningMessageResponse
from app.services.coach_opening import generate_coach_opening_message

router = APIRouter(prefix="/coach")
log = get_logger("app.api.v1.coach")


@router.get("/opening-message", response_model=CoachOpeningMessageResponse)
async def get_coach_opening_message(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CoachOpeningMessageResponse:
    """查询用户历史数据，并生成 Coach 页面个性化开场词。"""
    return await generate_coach_opening_message(db, user_id=user_id)


@router.post("/review")
async def start_coach_review(
    session_id: UUID = Query(..., description="面试会话 ID"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    启动教练复盘工作流，返回 SSE 流。
    """
    # 1. 验证 session 是否属于该用户
    stmt = select(InterviewSession).where(
        InterviewSession.id == session_id,
        InterviewSession.user_id == user_id
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=403, detail="无权访问该面试会话或会话不存在")
        
    if session.status != "completed":
        raise HTTPException(status_code=400, detail="面试尚未完成，无法复盘")

    # 2. 构造 SSE 生成器
    async def event_generator():
        try:
            state = {
                "user_id": user_id,
                "session_id": session_id,
                "db": db,
                "review_text": "",
                "plan_json": None,
                "plan_id": None,
                "candidate_memory": None,
                "last_session_report": None,
            }
            
            async for event in stream_coach_full_events(state):
                kind = event.get("kind")
                if kind == "token":
                    yield {
                        "event": "review_token",
                        "data": json.dumps({"token": event["token"]})
                    }
                elif kind == "node_update":
                    node = event.get("node")
                    data = event.get("data")
                    if node == "plan":
                        yield {
                            "event": "plan_done",
                            "data": json.dumps(data.get("plan_json", {}))
                        }
                    elif node == "persist":
                        plan_id = data.get("plan_id")
                        yield {
                            "event": "final",
                            "data": json.dumps({"plan_id": str(plan_id) if plan_id else None})
                        }
        except asyncio.CancelledError:
            log.info("coach_review_cancelled")
            raise
        except Exception as exc:
            log.error("coach_review_sse_failed", error=str(exc))
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": "教练复盘流水线失败", "code": "coach_review_error"},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_generator())


@router.get("/plans/latest")
async def get_latest_plan(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取用户最新一份未消费的教练计划。"""
    stmt = (
        select(CoachPlan)
        .where(CoachPlan.user_id == user_id, CoachPlan.consumed.is_(False))
        .order_by(desc(CoachPlan.created_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none()

    if not plan:
        return {"code": 200, "msg": "success", "data": None}

    data = CoachPlanResponse(
        id=plan.id,
        session_id=plan.session_id,
        plan_json=plan.plan_json,
        created_at=plan.created_at.isoformat(),
        consumed=plan.consumed,
    )
    return {"code": 200, "msg": "success", "data": data}
