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
        from app.core.config import get_settings

        r = Redis.from_url(get_settings().redis_url)
        pong = await r.ping()
        await r.close()
        redis_ok = bool(pong)
    except Exception:
        redis_ok = False

    return Response.ok(data={
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "db": db_ok,
        "redis": redis_ok,
    })
