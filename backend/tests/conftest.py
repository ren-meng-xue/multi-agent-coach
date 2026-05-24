"""pytest 全局 fixture：提供异步数据库会话，测试结束后自动回滚。"""
import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory


@pytest.fixture(scope="session")
def event_loop():
    """session 级别的事件循环，所有异步测试共用。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """每次测试提供独立 AsyncSession，teardown 自动 rollback 避免脏数据。"""
    async with async_session_factory() as session:
        try:
            await session.execute(text("SELECT 1"))
        except Exception as exc:
            pytest.skip(f"database unavailable: {exc}")
        yield session
        await session.rollback()
