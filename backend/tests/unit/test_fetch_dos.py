from unittest.mock import MagicMock, patch

import pytest

from app.services.jd_extractor import _fetch_url


class MockStreamResponse:
    def __init__(self, chunks, status_code=200):
        self.chunks = chunks
        self.status_code = status_code
        self.headers = {}
        self.encoding = "utf-8"

    async def aiter_bytes(self, chunk_size=4096):
        for chunk in self.chunks:
            yield chunk

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_fetch_url_enforces_2mb_size_limit():
    # 模拟一个会产生超过 2MB 的流（3块，每块 1MB，总共 3MB）
    over_limit_chunks = [b"A" * (1024 * 1024)] * 3
    mock_resp = MockStreamResponse(over_limit_chunks, status_code=200)

    # 模拟 SafeAsyncHTTPTransport 和 httpx.AsyncClient.stream
    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_resp)

    # 用 patch 模拟 httpx.AsyncClient 的 aenter
    async def mock_client_enter(*args, **kwargs):
        return mock_client

    with patch("app.services.jd_extractor.get_safe_url_ip", return_value="93.184.216.34"), \
         patch("httpx.AsyncClient.__aenter__", side_effect=mock_client_enter):
        
        result = await _fetch_url("https://example.com/huge-jd")
        
        # 验证因为文件超大而返回 None
        assert result is None
