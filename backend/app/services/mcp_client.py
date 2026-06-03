"""MCP client 单例：连接 job-intel MCP server，缓存工具列表，失败时优雅降级。

设计要点：
- 进程级单例，启动期一次建立连接，跨节点复用
- 失败不抛异常（连接失败返回空列表），让上游 Supervisor 走降级路径
- 缓存工具列表，避免每次工具查找都重新拉取
"""
from __future__ import annotations

from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.services.mcp_client")

_client: MultiServerMCPClient | None = None
_tools_cache: list[Any] | None = None


async def get_mcp_tools() -> list[Any]:
    """返回 LangChain BaseTool 列表（已封装 job-intel MCP server 的工具）。

    首次调用建立连接 + 拉取工具，后续调用走缓存。
    连接失败返回空列表（不抛异常），让 Supervisor 走 jd_analysis 兜底。
    """
    global _client, _tools_cache
    if _tools_cache is not None:
        return _tools_cache

    settings = get_settings()
    try:
        _client = MultiServerMCPClient({
            "job_intel": {
                "url": settings.mcp_job_intel_url,
                "transport": "streamable_http",
            }
        })
        _tools_cache = await _client.get_tools()
        log.info(
            "mcp_tools_loaded",
            url=settings.mcp_job_intel_url,
            count=len(_tools_cache),
            names=[t.name for t in _tools_cache],
        )
    except Exception as exc:
        log.warning(
            "mcp_connection_failed_fallback",
            url=settings.mcp_job_intel_url,
            error=str(exc),
        )
        _tools_cache = []
        _client = None

    return _tools_cache


async def get_tool(name: str) -> Any | None:
    """按名字找单个工具；找不到返回 None。"""
    tools = await get_mcp_tools()
    for t in tools:
        if t.name == name:
            return t
    return None


def reset_cache() -> None:
    """测试用：清空缓存。"""
    global _client, _tools_cache
    _client = None
    _tools_cache = None
