"""验证 Clerk JWT 鉴权中间件：空 token 拒绝，合法 token 放行。"""
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt import encode

from app.core.auth import decode_clerk_token, get_current_user_id


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
    token = encode({"sub": "user_123", "iss": "https://clerk.example.dev"}, private_pem, algorithm="RS256")

    assert decode_clerk_token(token, public_pem, issuer="https://clerk.example.dev") == "user_123"


def test_decode_clerk_token_rejects_wrong_issuer(rsa_key_pair):
    """issuer 不匹配的 token 必须拒绝，避免跨实例 token 混用。"""
    private_pem, public_pem = rsa_key_pair
    token = encode({"sub": "user_123", "iss": "https://evil.example.dev"}, private_pem, algorithm="RS256")

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token(token, public_pem, issuer="https://clerk.example.dev")

    assert exc.value.status_code == 401


def test_decode_clerk_token_rejects_expired_token(rsa_key_pair):
    """过期 token 必须被拒，避免长期有效凭证被重放。"""
    import time

    private_pem, public_pem = rsa_key_pair
    token = encode({"sub": "user_123", "exp": int(time.time()) - 10}, private_pem, algorithm="RS256")

    with pytest.raises(HTTPException) as exc:
        decode_clerk_token(token, public_pem)

    assert exc.value.status_code == 401


def test_decode_clerk_token_rejects_missing_public_key():
    """未配置公钥时必须返回明确 401，绝不能放行。"""
    with pytest.raises(HTTPException) as exc:
        decode_clerk_token("any.jwt.token", "")

    assert exc.value.status_code == 401
    assert "not configured" in exc.value.detail


def test_is_clerk_configured_reflects_public_key(monkeypatch):
    """is_clerk_configured 必须与鉴权同源：有公钥为 True，无公钥为 False。"""
    from app.core import auth

    monkeypatch.setattr(auth, "get_clerk_public_key", lambda: "some-public-key")
    assert auth.is_clerk_configured() is True

    monkeypatch.setattr(auth, "get_clerk_public_key", lambda: "")
    assert auth.is_clerk_configured() is False
