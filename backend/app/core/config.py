from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logging import get_logger

log = get_logger("app.core.config")


class Settings(BaseSettings):
    """应用全局配置，从 .env 文件和系统环境变量加载。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # 应用基础
    app_env: str = "dev"
    app_name: str = "multi-agent-coach"
    log_level: str = "INFO"

    # 数据库与缓存
    database_url: str
    redis_url: str

    # OpenAI
    openai_api_key: SecretStr
    openai_model_chat: str = "gpt-4o"
    openai_model_coach: str = "gpt-4o-mini"
    openai_model_embedding: str = "text-embedding-3-small"

    # Firecrawl 爬取
    firecrawl_api_key: SecretStr

    # Clerk 鉴权：JWT PEM 公钥，从 Clerk Dashboard → JWT Templates → Copy public key
    clerk_jwt_key: str
    clerk_issuer: str = ""

    # 跨域白名单
    cors_origins: list[str] = ["http://localhost:3000"]


def _warn_if_clerk_misconfigured(settings: Settings) -> None:
    """配了公钥但缺 issuer 时告警：此时 JWT 的 issuer 不会被校验，是安全弱化。"""
    if settings.clerk_jwt_key and not settings.clerk_issuer:
        log.warning("clerk_issuer_missing")


@lru_cache
def get_settings() -> Settings:
    """返回缓存的单例 Settings 实例，用于依赖注入（避免每请求重复解析配置）。"""
    s = Settings()
    _warn_if_clerk_misconfigured(s)
    return s
