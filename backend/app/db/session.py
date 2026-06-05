"""异步数据库引擎与会话工厂，提供 FastAPI 依赖注入用 get_db。"""
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

def _build_engine_args(database_url: str) -> tuple[str, dict]:
    """asyncpg 不接受 sslmode 查询参数（这是 libpq/psycopg2 方言）。
    遇到 sslmode=require 时剥离该参数并改用 connect_args ssl=True。
    """
    parsed = urlparse(database_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    sslmode = params.pop("sslmode", [None])[0]

    new_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=new_query))

    connect_args: dict = {}
    if sslmode in ("require", "verify-ca", "verify-full"):
        connect_args["ssl"] = True

    return clean_url, connect_args


_db_url, _connect_args = _build_engine_args(settings.database_url)

engine = create_async_engine(
    _db_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：每次请求生成一个 AsyncSession，结束后自动关闭。"""
    async with async_session_factory() as session:
        yield session
