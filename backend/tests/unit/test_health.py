"""验证健康检查的连通性探测：失败路径必须记录 warning，不能静默吞异常。"""
import structlog

from app.api.v1 import health


async def test_check_db_returns_true_on_success():
    """db 正常时返回 True，且不误报失败日志。"""
    from unittest.mock import AsyncMock

    m = AsyncMock()
    with structlog.testing.capture_logs() as logs:
        ok = await health._check_db(m)

    assert ok is True
    assert not any(e.get("event") == "health_db_check_failed" for e in logs)


async def test_check_db_logs_warning_on_failure():
    """db 检查失败必须返回 False 并记录 warning，而非静默吞异常。"""
    from unittest.mock import AsyncMock

    m = AsyncMock()
    m.execute.side_effect = RuntimeError("db down")
    with structlog.testing.capture_logs() as logs:
        ok = await health._check_db(m)

    assert ok is False
    assert any(e.get("event") == "health_db_check_failed" for e in logs)


async def test_check_redis_logs_warning_on_failure(monkeypatch):
    """redis 检查失败必须返回 False 并记录 warning，而非静默吞异常。"""
    import redis.asyncio

    class _BoomRedis:
        """模拟连接即失败的 Redis，避免测试依赖真实服务。"""

        @staticmethod
        def from_url(url):
            raise RuntimeError("redis down")

    monkeypatch.setattr(redis.asyncio, "Redis", _BoomRedis)
    with structlog.testing.capture_logs() as logs:
        ok = await health._check_redis("redis://localhost:6379/0")

    assert ok is False
    assert any(e.get("event") == "health_redis_check_failed" for e in logs)


async def test_check_redis_closes_client_when_ping_fails(monkeypatch):
    """ping 抛错时仍必须关闭 Redis client，避免健康检查泄漏连接。"""
    import redis.asyncio

    class _FailingRedis:
        closed = False

        @staticmethod
        def from_url(url, **kwargs):
            return _FailingRedis()

        async def ping(self):
            raise RuntimeError("redis ping failed")

        async def aclose(self):
            _FailingRedis.closed = True

    monkeypatch.setattr(redis.asyncio, "Redis", _FailingRedis)

    ok = await health._check_redis("redis://localhost:6379/0")

    assert ok is False
    assert _FailingRedis.closed is True
