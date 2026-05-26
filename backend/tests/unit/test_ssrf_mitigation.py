from unittest.mock import AsyncMock, patch

import pytest

from app.services.jd_extractor import (
    SafeAsyncNetworkBackend,
    _fetch_url,
    get_safe_url_ip,
    is_safe_url,
)


def test_get_safe_url_ip_loopback_and_private():
    # 测试回环地址和内网保留地址
    assert get_safe_url_ip("http://127.0.0.1/abc") is None
    assert get_safe_url_ip("https://192.168.1.100/test") is None
    assert get_safe_url_ip("http://10.0.0.1") is None
    assert get_safe_url_ip("http://169.254.169.254/metadata") is None
    assert get_safe_url_ip("http://localhost") is None


def test_get_safe_url_ip_invalid_scheme_and_host():
    assert get_safe_url_ip("ftp://google.com") is None
    assert get_safe_url_ip("http://") is None


def test_is_safe_url():
    assert is_safe_url("http://127.0.0.1") is False
    assert is_safe_url("https://192.168.0.1") is False


@pytest.mark.asyncio
async def test_safe_async_network_backend_pins_ip():
    # 验证 SafeAsyncNetworkBackend 的 connect_tcp 会强行将外部域名 host 改为 Pin 定的安全 IP
    mock_backend = AsyncMock()
    allowed_ip = "93.184.216.34" # example.com
    
    backend = SafeAsyncNetworkBackend(allowed_ip=allowed_ip)
    # 替换内部底层的 _backend 
    backend._backend = mock_backend
    
    await backend.connect_tcp(host="example.com", port=443)
    
    # 确认底层的 connect_tcp 是由 Pin 定的 IP 发起的，而不是域名，防止二次解析
    mock_backend.connect_tcp.assert_called_once_with(
        host=allowed_ip,
        port=443,
        timeout=None,
        local_address=None,
        socket_options=None
    )


@pytest.mark.asyncio
async def test_fetch_url_blocked_by_ssrf():
    # 验证当 URL 指向不安全 IP 时，_fetch_url 直接返回 None，不发生连接
    with patch("app.services.jd_extractor.get_safe_url_ip", return_value=None):
        result = await _fetch_url("http://127.0.0.1")
        assert result is None
