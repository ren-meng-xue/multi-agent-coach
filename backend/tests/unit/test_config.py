from app.core.config import Settings


def test_settings_loads_required_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    monkeypatch.setenv("CLERK_JWT_KEY", "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----")
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.dev")
    monkeypatch.setenv("CLERK_JWT_AUDIENCE", "multi-agent-coach")
    s = Settings()
    assert s.database_url == "postgresql+asyncpg://u:p@h:5432/db"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.openai_api_key.get_secret_value() == "sk-test"
    assert s.firecrawl_api_key.get_secret_value() == "fc-test"
    assert "PUBLIC KEY" in s.clerk_jwt_key
    assert s.clerk_issuer == "https://clerk.example.dev"
    assert s.clerk_jwt_audience == "multi-agent-coach"
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


def test_settings_supports_authorized_party_for_clerk_session_token(monkeypatch):
    """Clerk session token 没有 aud 时，可通过 azp/authorized party 配置校验用途。"""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    monkeypatch.setenv("CLERK_JWT_KEY", "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----")
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.dev")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTY", "http://localhost:3000")

    s = Settings()

    assert s.clerk_authorized_party == "http://localhost:3000"
