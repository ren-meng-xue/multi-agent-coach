"""认证相关接口：暴露当前 Clerk 登录用户信息。"""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id
from app.schemas.response import Response

router = APIRouter(prefix="/auth")


@router.get("/me")
async def me(user_id: str = Depends(get_current_user_id)):
    """返回当前 Clerk 已认证用户 id，供前端验证登录态与后端鉴权链路。"""
    return Response.ok(data={"user_id": user_id})
