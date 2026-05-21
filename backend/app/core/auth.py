"""Clerk JWT 鉴权中间件：从 Authorization header 解析 user_id，用于所有需要登录的接口。"""
import jwt
from fastapi import Header, HTTPException

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.core.auth")


def get_clerk_public_key() -> str:
    """读取 Clerk JWT 公钥，优先使用配置，开发环境兼容本地 clerk-public.pem。"""
    settings = get_settings()
    if settings.clerk_jwt_key:
        return settings.clerk_jwt_key
    try:
        with open("clerk-public.pem") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def is_clerk_configured() -> bool:
    """鉴权是否就绪：能取得公钥即可对外校验 token，供健康检查与鉴权共用同一判断。"""
    return bool(get_clerk_public_key())


def decode_clerk_token(token: str, public_key: str, issuer: str = "") -> str:
    """校验 Clerk RS256 JWT 并返回 sub 作为业务 user_id。"""
    if not public_key:
        log.warning("clerk_public_key_missing")
        raise HTTPException(status_code=401, detail="clerk jwt key is not configured")

    options = {"verify_aud": False, "verify_iat": True}
    decode_kwargs = {"issuer": issuer} if issuer else {}

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options=options,
            **decode_kwargs,
        )
        sub = payload.get("sub")
        if not sub:
            log.warning("clerk_token_missing_sub")
            raise HTTPException(status_code=401, detail="token missing sub claim")
        return sub
    except HTTPException:
        raise
    except jwt.PyJWTError as exc:
        log.warning("clerk_token_invalid", error=str(exc))
        raise HTTPException(status_code=401, detail="invalid token") from exc


async def get_current_user_id(
    authorization: str = Header(..., description="Bearer <clerk_jwt>"),
) -> str:
    """FastAPI 依赖：从 Authorization header 校验 Clerk JWT，返回 user_id。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or invalid authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="empty token")

    settings = get_settings()
    return decode_clerk_token(token, get_clerk_public_key(), issuer=settings.clerk_issuer)


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
