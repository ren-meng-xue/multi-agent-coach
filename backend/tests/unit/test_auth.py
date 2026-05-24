"""验证 Clerk JWT 鉴权中间件：空 token 拒绝，合法 token 放行。"""
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt import encode

from app.core.auth import decode_clerk_token, get_current_user_id

ISSUER = "https://clerk.example.dev"
AUDIENCE = "multi-agent-coach"
AUTHORIZED_PARTY = "http://localhost:3000"


@pytest.fixture
def rsa_key_pair():
    """生成测试用 RSA 密钥对，模拟 Clerk RS256 JWT。"""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem.decode("utf-8")


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


def test_decode_clerk_token_accepts_valid_rs256_token(rsa_key_pair):
    """合法 Clerk RS256 token 必须解析出 sub。"""
    private_pem, public_pem = rsa_key_pair
    token = encode(
        {"sub": "user_123", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 3600},
        private_pem,
        algorithm="RS256",
    )

    assert decode_clerk_token(token, public_pem, issuer=ISSUER, audience=AUDIENCE) == "user_123"


def test_decode_clerk_token_accepts_valid_authorized_party(rsa_key_pair):
    """无 aud 时可通过 Clerk azp 校验 token 的前端来源。"""
    private_pem, public_pem = rsa_key_pair
    token = encode(
        {"sub": "user_123", "iss": ISSUER, "azp": AUTHORIZED_PARTY, "exp": int(time.time()) + 3600},
        private_pem,
        algorithm="RS256",
    )

    assert (
        decode_clerk_token(
            token,
            public_pem,
            issuer=ISSUER,
            authorized_party=AUTHORIZED_PARTY,
        )
        == "user_123"
    )


def test_decode_clerk_token_rejects_wrong_issuer(rsa_key_pair):
    """issuer 不匹配的 token 必须拒绝，避免跨实例 token 混用。"""
    private_pem, public_pem = rsa_key_pair
    token = encode(
        {"sub": "user_123", "iss": "https://evil.example.dev", "aud": AUDIENCE, "exp": int(time.time()) + 3600},
        private_pem,
        algorithm="RS256",
    )

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token(token, public_pem, issuer=ISSUER, audience=AUDIENCE)

    assert exc.value.status_code == 401


def test_decode_clerk_token_rejects_wrong_audience(rsa_key_pair):
    """audience 不匹配的 token 必须拒绝，避免其他用途 token 被复用。"""
    private_pem, public_pem = rsa_key_pair
    token = encode(
        {"sub": "user_123", "iss": ISSUER, "aud": "other-api", "exp": int(time.time()) + 3600},
        private_pem,
        algorithm="RS256",
    )

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token(token, public_pem, issuer=ISSUER, audience=AUDIENCE)

    assert exc.value.status_code == 401


def test_decode_clerk_token_rejects_wrong_authorized_party(rsa_key_pair):
    """azp 不匹配的 token 必须拒绝，避免非预期前端来源复用 token。"""
    private_pem, public_pem = rsa_key_pair
    token = encode(
        {"sub": "user_123", "iss": ISSUER, "azp": "http://evil.example.dev", "exp": int(time.time()) + 3600},
        private_pem,
        algorithm="RS256",
    )

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token(
            token,
            public_pem,
            issuer=ISSUER,
            authorized_party=AUTHORIZED_PARTY,
        )

    assert exc.value.status_code == 401


def test_decode_clerk_token_rejects_expired_token(rsa_key_pair):
    """过期 token 必须被拒，避免长期有效凭证被重放。"""
    private_pem, public_pem = rsa_key_pair
    token = encode(
        {"sub": "user_123", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) - 10},
        private_pem,
        algorithm="RS256",
    )

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token(token, public_pem, issuer=ISSUER, audience=AUDIENCE)

    assert exc.value.status_code == 401


def test_decode_clerk_token_rejects_token_without_exp(rsa_key_pair):
    """缺少 exp 的令牌必须被拒：PyJWT 仅在 exp 存在时才查过期，缺 exp 会被当作永不过期放行。"""
    private_pem, public_pem = rsa_key_pair
    token = encode({"sub": "user_123", "iss": ISSUER, "aud": AUDIENCE}, private_pem, algorithm="RS256")

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token(token, public_pem, issuer=ISSUER, audience=AUDIENCE)

    assert exc.value.status_code == 401


def test_decode_clerk_token_rejects_missing_public_key():
    """未配置公钥时必须返回明确 401，绝不能放行。"""
    with pytest.raises(HTTPException) as exc:
        decode_clerk_token("any.jwt.token", "", issuer=ISSUER, audience=AUDIENCE)

    assert exc.value.status_code == 401
    assert "not configured" in exc.value.detail


def test_decode_clerk_token_rejects_missing_issuer(rsa_key_pair):
    """缺 issuer 配置时必须拒绝，不能降级为不校验 issuer。"""
    private_pem, public_pem = rsa_key_pair
    token = encode({"sub": "user_123", "iss": ISSUER, "aud": AUDIENCE}, private_pem, algorithm="RS256")

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token(token, public_pem, issuer="", audience=AUDIENCE)

    assert exc.value.status_code == 401


def test_decode_clerk_token_rejects_missing_token_purpose_config(rsa_key_pair):
    """缺 audience/azp 配置时必须拒绝，不能接受任意用途 token。"""
    private_pem, public_pem = rsa_key_pair
    token = encode({"sub": "user_123", "iss": ISSUER}, private_pem, algorithm="RS256")

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token(token, public_pem, issuer=ISSUER)

    assert exc.value.status_code == 401


def test_is_clerk_configured_reflects_required_auth_settings(monkeypatch):
    """is_clerk_configured 必须与鉴权同源：缺任一关键校验项都不是就绪状态。"""
    from types import SimpleNamespace

    from app.core import auth

    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            clerk_jwt_key="some-public-key",
            clerk_issuer=ISSUER,
            clerk_jwt_audience=AUDIENCE,
            clerk_authorized_party="",
        ),
    )
    assert auth.is_clerk_configured() is True

    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            clerk_jwt_key="some-public-key",
            clerk_issuer="",
            clerk_jwt_audience=AUDIENCE,
            clerk_authorized_party="",
        ),
    )
    assert auth.is_clerk_configured() is False
