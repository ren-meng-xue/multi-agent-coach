# backend/app/services/jd_extractor.py
"""JD text extraction: text / PDF / DOCX / URL → plain string."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Literal

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


def extract_jd_text(source: JDSource) -> str:
    """同步提取（text/file）。URL 和 image 请用 extract_jd_text_async。"""
    if source.type == "text":
        return source.content.strip()
    if source.type == "file":
        if source.filename.lower().endswith(".pdf"):
            return _parse_pdf(source.content_bytes)
        if source.filename.lower().endswith((".docx", ".doc")):
            return _parse_docx(source.content_bytes)
        raise ValueError(f"Unsupported file type: {source.filename}")
    raise ValueError(f"Use extract_jd_text_async for type: {source.type}")


async def extract_jd_text_async(source: JDSource) -> str:
    """异步提取（支持全部4种来源）。"""
    if source.type in ("text", "file"):
        return extract_jd_text(source)
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


async def _fetch_url(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                log.warning("jd_url_fetch_failed", url=url, status=resp.status_code)
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return text[:8000] if text else None
    except Exception as exc:
        log.warning("jd_url_fetch_error", url=url, error=str(exc))
        return None


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
