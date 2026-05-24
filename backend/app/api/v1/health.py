"""健康检查端点：验证数据库和 Redis 连通性。"""
import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.response import Response

router = APIRouter()
log = get_logger("app.api.v1.health")


async def _check_db(db: AsyncSession, timeout_seconds: float = 2.0) -> bool:
    """检查数据库连通性；失败时记录 warning，避免静默吞异常。"""
    try:
        async with asyncio.timeout(timeout_seconds):
            await db.execute(text("SELECT 1"))
        return True
    except TimeoutError as exc:
        log.warning("health_db_check_timeout", error=str(exc))
        return False
    except Exception as exc:
        log.warning("health_db_check_failed", error=str(exc))
        return False


async def _check_redis(redis_url: str, timeout_seconds: float = 2.0) -> bool:
    """检查 Redis 连通性；失败时记录 warning，避免静默吞异常。"""
    r = None
    try:
        from redis.asyncio import Redis

        r = Redis.from_url(
            redis_url,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
        )
        async with asyncio.timeout(timeout_seconds):
            pong = await r.ping()
        return bool(pong)
    except TimeoutError as exc:
        log.warning("health_redis_check_timeout", error=str(exc))
        return False
    except Exception as exc:
        log.warning("health_redis_check_failed", error=str(exc))
        return False
    finally:
        if r is not None:
            try:
                await r.aclose()
            except Exception as exc:
                log.warning("health_redis_close_failed", error=str(exc))


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """返回服务健康状态，包含 db、redis、clerk 的检查结果。"""
    from app.core.auth import is_clerk_configured
    from app.core.config import get_settings

    settings = get_settings()
    db_ok = await _check_db(db)
    redis_ok = await _check_redis(settings.redis_url)
    # 与鉴权链路同源：is_clerk_configured 要求公钥、issuer 与 aud/azp 校验项均已配置才算就绪
    clerk_ok = is_clerk_configured()

    return Response.ok(data={
        "status": "ok" if (db_ok and redis_ok and clerk_ok) else "degraded",
        "db": db_ok,
        "redis": redis_ok,
        "clerk": clerk_ok,
    })
