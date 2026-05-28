"""教练复盘相关的 Pydantic 模型。"""
from uuid import UUID

from pydantic import BaseModel


class CoachPlanResponse(BaseModel):
    """教练计划的响应模型。"""
    id: UUID
    session_id: UUID | None
    plan_json: dict
    created_at: str
    consumed: bool

class CoachReviewEvent(BaseModel):
    """教练复盘 SSE 事件模型。"""
    event: str  # review_token, plan_done, final, error
    data: dict
