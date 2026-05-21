"""健康检查端点：验证数据库和 Redis 连通性。"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.response import Response

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """返回服务健康状态，包含 db 和 redis 的连通性检查结果。"""
    from app.core.config import get_settings

    settings = get_settings()

    # 检查数据库连通性
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    # 检查 Redis 连通性
    redis_ok = False
    try:
        from redis.asyncio import Redis

        r = Redis.from_url(settings.redis_url)
        pong = await r.ping()
        await r.close()
        redis_ok = bool(pong)
    except Exception:
        redis_ok = False

    # 与鉴权链路同源判断：能取得公钥即视为 Clerk 就绪（缺 issuer 由配置告警暴露，不阻断健康）
    from app.core.auth import is_clerk_configured

    clerk_ok = is_clerk_configured()

    return Response.ok(data={
        "status": "ok" if (db_ok and redis_ok and clerk_ok) else "degraded",
        "db": db_ok,
        "redis": redis_ok,
        "clerk": clerk_ok,
    })
