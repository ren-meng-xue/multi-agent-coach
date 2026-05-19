"""Clerk JWT 鉴权中间件：从 Authorization header 解析 user_id，用于所有需要登录的接口。"""
import jwt
from fastapi import Header, HTTPException

from app.core.config import get_settings

_settings = get_settings()

# D1 阶段：优先读环境变量 CLERK_JWT_KEY，缺省尝试本地 clerk-public.pem 文件
# 生产环境应只走环境变量
try:
    with open("clerk-public.pem") as f:
        _pem = f.read()
except FileNotFoundError:
    _pem = _settings.clerk_jwt_key or ""


async def get_current_user_id(
    authorization: str = Header(..., description="Bearer <clerk_jwt>"),
) -> str:
    """FastAPI 依赖：从 Authorization header 校验 Clerk JWT，返回 user_id。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or invalid authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="empty token")

    try:
        payload = jwt.decode(
            token,
            _pem,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iat": True},
        )
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="token missing sub claim")
        return sub
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"invalid token: {exc}")


async def get_optional_user_id(
    authorization: str | None = Header(None, description="Optional Bearer <clerk_jwt>"),
) -> str | None:
    """可选鉴权：有 token 则解析，无则返回 None，用于可匿名访问的端点。"""
    if not authorization:
        return None
    try:
        return await get_current_user_id(authorization=authorization)
    except HTTPException:
        return None
