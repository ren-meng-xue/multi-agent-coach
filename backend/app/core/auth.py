"""Clerk JWT 鉴权中间件：从 Authorization header 解析 user_id，用于所有需要登录的接口。"""
import jwt
from fastapi import Header, HTTPException
from jwt.types import Options

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.core.auth")


def get_clerk_public_key() -> str:
    """从配置读取 Clerk JWT 公钥。"""
    settings = get_settings()
    return settings.clerk_jwt_key


def is_clerk_configured() -> bool:
    """鉴权是否就绪：公钥、issuer 与 token 用途校验项均已配置。"""
    settings = get_settings()
    return bool(
        settings.clerk_jwt_key
        and settings.clerk_issuer
        and (settings.clerk_jwt_audience or settings.clerk_authorized_party)
    )


def decode_clerk_token(
    token: str,
    public_key: str,
    issuer: str,
    audience: str = "",
    authorized_party: str = "",
) -> str:
    """校验 Clerk RS256 JWT 并返回 sub 作为业务 user_id。"""
    if not public_key:
        log.warning("clerk_public_key_missing")
        raise HTTPException(status_code=401, detail="clerk jwt key is not configured")
    if not issuer:
        log.warning("clerk_issuer_missing")
        raise HTTPException(status_code=401, detail="clerk issuer is not configured")
    if not audience and not authorized_party:
        log.warning("clerk_token_purpose_check_missing")
        raise HTTPException(status_code=401, detail="clerk token audience is not configured")

    # 强制要求 exp：PyJWT 仅在 exp 存在时才校验过期，缺 exp 的令牌会被当作永不过期而放行
    options: Options = {"verify_aud": bool(audience), "verify_iat": True, "require": ["exp"]}

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options=options,
            issuer=issuer,
            audience=audience or None,
        )
        sub = payload.get("sub")
        if not sub:
            log.warning("clerk_token_missing_sub")
            raise HTTPException(status_code=401, detail="token missing sub claim")
        if authorized_party and payload.get("azp") != authorized_party:
            log.warning("clerk_token_invalid_authorized_party")
            raise HTTPException(status_code=401, detail="invalid token authorized party")
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
    return decode_clerk_token(
        token,
        get_clerk_public_key(),
        issuer=settings.clerk_issuer,
        audience=settings.clerk_jwt_audience,
        authorized_party=settings.clerk_authorized_party,
    )


async def get_optional_user_id(
    authorization: str | None = Header(None, description="Optional Bearer <clerk_jwt>"),
) -> str | None:
    """可选鉴权：有 token 则解析，无则返回 None，用于可匿名访问的端点。"""
    if not authorization:
        return None
    try:
        return await get_current_user_id(authorization=authorization)
    except HTTPException as exc:
        log.warning("optional_clerk_token_invalid", status_code=exc.status_code, detail=exc.detail)
        return None
