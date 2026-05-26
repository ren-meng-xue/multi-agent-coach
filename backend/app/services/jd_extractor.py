# backend/app/services/jd_extractor.py
"""JD text extraction: text / PDF / DOCX / URL → plain string."""
from __future__ import annotations

import asyncio
import io
import socket
import typing
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlparse

import httpcore
import httpx
from bs4 import BeautifulSoup

from app.core.logging import get_logger

log = get_logger("app.services.jd_extractor")


class NeedManualInput(Exception):
    """URL 爬取失败，需用户手动粘贴文本。"""


@dataclass
class JDSource:
    type: Literal["text", "file", "url", "image"]
    content: str = ""           # text 类型使用
    url: str = ""               # url 类型使用
    filename: str = ""          # file/image 类型使用
    content_bytes: bytes = field(default_factory=bytes)  # file/image 类型使用


async def extract_jd_text_async(source: JDSource) -> str:
    """异步提取（支持全部4种来源）。"""
    if source.type == "text":
        return source.content.strip()
    if source.type == "file":
        if source.filename.lower().endswith(".pdf"):
            return await asyncio.to_thread(_parse_pdf, source.content_bytes)
        if source.filename.lower().endswith((".docx", ".doc")):
            return await asyncio.to_thread(_parse_docx, source.content_bytes)
        raise ValueError(f"Unsupported file type: {source.filename}")
    if source.type == "url":
        text = await _fetch_url(source.url)
        if not text:
            raise NeedManualInput(
                "此链接需要登录或爬取失败，请直接粘贴 JD 文本。"
            )
        return text
    if source.type == "image":
        return await _extract_image_text(source.content_bytes)
    raise ValueError(f"Unknown source type: {source.type}")


def _parse_pdf(data: bytes) -> str:
    import PyPDF2  # lazy import
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    pages = [p.extract_text() or "" for p in reader.pages]
    return "\n".join(pages).strip()


def _parse_docx(data: bytes) -> str:
    import mammoth  # type: ignore[import-untyped]
    result = mammoth.extract_raw_text(io.BytesIO(data))
    return result.value.strip()


def get_safe_url_ip(url: str) -> str | None:
    """DNS 级别与保留 IP SSRF 校验。
    如果是安全 URL，则返回解析出的安全 IP 字符串，否则返回 None。
    """
    import ipaddress
    
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None
        hostname = parsed.hostname
        if not hostname:
            return None
        
        # 解析 DNS 并进行 IP 安全段校验
        addr_info = socket.getaddrinfo(hostname, None)
        if not addr_info:
            return None
            
        safe_ip = None
        for _, _, _, _, sockaddr in addr_info:
            ip_str = str(sockaddr[0])
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return None
            if not safe_ip:
                safe_ip = ip_str
        return safe_ip
    except Exception as exc:
        log.warning("ssrf_check_error", url=url, error=str(exc))
        return None


def is_safe_url(url: str) -> bool:
    """旧接口封装兼容，判断 URL 是否安全。"""
    return get_safe_url_ip(url) is not None


class SafeAsyncNetworkBackend(httpcore.AsyncNetworkBackend):
    """自定义 AnyIO Network Backend，将 TCP 连接强行锁定在指定安全 IP 上，防范 DNS Rebinding。"""
    def __init__(self, allowed_ip: str):
        self._backend = httpcore._backends.auto.AutoBackend()  # type: ignore[attr-defined]
        self.allowed_ip = allowed_ip

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: typing.Iterable[typing.Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        # 强制将物理连接地址更改为 allowed_ip，而外部 TLS 与 SNI 校验依然使用原 hostname
        return await self._backend.connect_tcp(
            host=self.allowed_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class SafeAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """自定义 HTTP 传输通道，强制底层连接池使用 Pin 定的安全 IP。"""
    def __init__(self, allowed_ip: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 重新创建 httpcore.AsyncConnectionPool，注入强制锁定 IP 的 network_backend
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            max_connections=self._pool._max_connections,
            max_keepalive_connections=self._pool._max_keepalive_connections,
            keepalive_expiry=self._pool._keepalive_expiry,
            http1=self._pool._http1,
            http2=self._pool._http2,
            network_backend=SafeAsyncNetworkBackend(allowed_ip),
        )


async def _fetch_url(url: str) -> str | None:
    from urllib.parse import urljoin

    
    # 限制最大读取大小为 2MB，防止 DoS 爆内存
    MAX_BYTES = 2 * 1024 * 1024

    try:
        current_url = url
        max_redirects = 3
        redirect_count = 0

        while redirect_count <= max_redirects:
            # 1. 在发起连接前，解析并获取安全的 IP (防范第二次 DNS 解析绕过)
            safe_ip = await asyncio.to_thread(get_safe_url_ip, current_url)
            if not safe_ip:
                log.warning("ssrf_blocked_unsafe_url", url=current_url)
                return None
                
            # 2. 为当前特定的 safe_ip 初始化专属的安全 Transport 和 Client，固定物理连接 IP
            transport = SafeAsyncHTTPTransport(allowed_ip=safe_ip, timeout=10)
            async with (
                httpx.AsyncClient(transport=transport, timeout=10, follow_redirects=False) as client,
                # 3. 使用 client.stream 流式处理请求，避免一次性加载超大文件
                client.stream("GET", current_url, headers={"User-Agent": "Mozilla/5.0"}) as resp,
            ):
                    if resp.status_code in (301, 302, 303, 307, 308):
                        redirect_url = resp.headers.get("Location")
                        if not redirect_url:
                            break
                        
                        redirect_url = urljoin(current_url, redirect_url)
                        current_url = redirect_url
                        redirect_count += 1
                    elif resp.status_code == 200:
                        chunks = []
                        bytes_received = 0
                        async for chunk in resp.aiter_bytes(chunk_size=4096):
                            chunks.append(chunk)
                            bytes_received += len(chunk)
                            if bytes_received > MAX_BYTES:
                                log.warning("jd_url_fetch_too_large", url=current_url, size=bytes_received)
                                return None
                                
                        body_bytes = b"".join(chunks)
                        encoding = resp.encoding or "utf-8"
                        try:
                            html_text = body_bytes.decode(encoding, errors="replace")
                        except Exception:
                            html_text = body_bytes.decode("utf-8", errors="replace")
                            
                        text = await asyncio.to_thread(_parse_html, html_text)
                        return text
                    else:
                        log.warning("jd_url_fetch_failed", url=current_url, status=resp.status_code)
                        return None

        if redirect_count > max_redirects:
            log.warning("ssrf_too_many_redirects", url=url)
            return None
        return None
    except Exception as exc:
        log.warning("jd_url_fetch_error", url=url, error=str(exc))
        return None


def _parse_html(html_text: str) -> str | None:
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return text[:8000] if text else None


async def _extract_image_text(image_bytes: bytes) -> str:
    """使用 GPT-4o Vision 从图片截图提取 JD 文本。"""
    import base64

    from langchain_core.messages import HumanMessage
    from langchain_openai import ChatOpenAI

    from app.core.config import get_settings

    settings = get_settings()
    model = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.openai_api_key,
        timeout=30,
    )
    b64 = base64.standard_b64encode(image_bytes).decode()
    message = HumanMessage(
        content=[
            {"type": "text", "text": "请提取图片中的所有文字内容，保持原有格式，不要添加任何解释。"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            },
        ]
    )
    msg = await model.ainvoke([message])
    return str(msg.content)
