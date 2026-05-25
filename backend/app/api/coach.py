"""Coach 页面接口。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.db.session import get_db
from app.schemas.interview import CoachOpeningMessageResponse
from app.services.coach_opening import generate_coach_opening_message

router = APIRouter(prefix="/coach")


@router.get("/opening-message", response_model=CoachOpeningMessageResponse)
async def get_coach_opening_message(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CoachOpeningMessageResponse:
    """查询用户历史数据，并生成 Coach 页面个性化开场词。"""
    return await generate_coach_opening_message(db, user_id=user_id)
