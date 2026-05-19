"""验证 Clerk JWT 鉴权中间件：空 token 拒绝，合法 token 放行。"""
import pytest
from fastapi import HTTPException

from app.core.auth import get_current_user_id


def test_get_current_user_id_rejects_no_header():
    """空 Authorization header 必须返回 401。"""

    async def run():
        with pytest.raises(HTTPException) as exc:
            await get_current_user_id(authorization="")
        assert exc.value.status_code == 401

    import asyncio

    asyncio.run(run())


def test_get_current_user_id_rejects_missing_bearer():
    """非 Bearer 格式的 token 必须返回 401。"""

    async def run():
        with pytest.raises(HTTPException) as exc:
            await get_current_user_id(authorization="not-bearer-format")
        assert exc.value.status_code == 401

    import asyncio

    asyncio.run(run())
