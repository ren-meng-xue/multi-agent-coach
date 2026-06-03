"""MCP client 单例 / 重试 / 降级测试。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_mcp_tools_caches_after_first_call():
    """get_mcp_tools 应只建立一次连接，第二次直接拿缓存。"""
    from app.services import mcp_client

    # 复位模块级缓存
    mcp_client._tools_cache = None
    mcp_client._client = None

    fake_tool = MagicMock(name="extract_jd_text")
    fake_tool.name = "extract_jd_text"

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[fake_tool])

    with patch(
        "app.services.mcp_client.MultiServerMCPClient",
        return_value=mock_client,
    ) as mock_ctor:
        t1 = await mcp_client.get_mcp_tools()
        t2 = await mcp_client.get_mcp_tools()

    assert t1 == [fake_tool]
    assert t2 == [fake_tool]
    mock_ctor.assert_called_once()                 # 构造一次
    mock_client.get_tools.assert_awaited_once()    # get_tools 一次


@pytest.mark.asyncio
async def test_get_mcp_tools_returns_empty_when_connection_fails():
    """连接失败时返回空列表，让上游降级，不抛异常。"""
    from app.services import mcp_client

    mcp_client._tools_cache = None
    mcp_client._client = None

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(side_effect=ConnectionError("refused"))

    with patch(
        "app.services.mcp_client.MultiServerMCPClient",
        return_value=mock_client,
    ):
        result = await mcp_client.get_mcp_tools()

    assert result == []


@pytest.mark.asyncio
async def test_get_tool_by_name_finds_target():
    """get_tool 按名字找到具体工具。"""
    from app.services import mcp_client

    mcp_client._tools_cache = None
    mcp_client._client = None

    t1 = MagicMock(); t1.name = "extract_jd_text"
    t2 = MagicMock(); t2.name = "web_search"

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[t1, t2])

    with patch(
        "app.services.mcp_client.MultiServerMCPClient",
        return_value=mock_client,
    ):
        result = await mcp_client.get_tool("web_search")

    assert result is t2


@pytest.mark.asyncio
async def test_get_tool_returns_none_when_not_found():
    """工具不存在时返回 None，不抛异常。"""
    from app.services import mcp_client

    mcp_client._tools_cache = None
    mcp_client._client = None

    t1 = MagicMock(); t1.name = "extract_jd_text"
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[t1])

    with patch(
        "app.services.mcp_client.MultiServerMCPClient",
        return_value=mock_client,
    ):
        result = await mcp_client.get_tool("nonexistent")

    assert result is None
