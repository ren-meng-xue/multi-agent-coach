from app.core.config import Settings


def test_settings_loads_required_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    monkeypatch.setenv("CLERK_JWT_KEY", "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----")
    s = Settings()
    assert s.database_url == "postgresql+asyncpg://u:p@h:5432/db"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.openai_api_key.get_secret_value() == "sk-test"
    assert s.firecrawl_api_key.get_secret_value() == "fc-test"
    assert "PUBLIC KEY" in s.clerk_jwt_key
    assert s.app_env in {"dev", "test", "prod"}


def test_settings_missing_required_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_is_cached():
    """get_settings 应缓存为单例，避免每个请求重复解析配置。"""
    from app.core.config import get_settings

    assert get_settings() is get_settings()


def test_warn_if_clerk_misconfigured_warns_when_issuer_missing():
    """配了公钥但缺 issuer 时必须告警：此时 token 的 issuer 不会被校验。"""
    import structlog

    from app.core import config

    s = config.Settings(
        clerk_jwt_key="-----BEGIN PUBLIC KEY-----\nx\n-----END PUBLIC KEY-----",
        clerk_issuer="",
    )
    with structlog.testing.capture_logs() as logs:
        config._warn_if_clerk_misconfigured(s)

    assert any(e.get("event") == "clerk_issuer_missing" for e in logs)


def test_warn_if_clerk_misconfigured_silent_when_issuer_set():
    """issuer 已配置时不应告警。"""
    import structlog

    from app.core import config

    s = config.Settings(
        clerk_jwt_key="-----BEGIN PUBLIC KEY-----\nx\n-----END PUBLIC KEY-----",
        clerk_issuer="https://clerk.example.dev",
    )
    with structlog.testing.capture_logs() as logs:
        config._warn_if_clerk_misconfigured(s)

    assert not any(e.get("event") == "clerk_issuer_missing" for e in logs)
