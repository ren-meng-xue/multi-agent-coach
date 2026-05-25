# backend/tests/unit/test_jd_extractor.py
import pytest
from unittest.mock import AsyncMock, patch

from app.services.jd_extractor import (
    extract_jd_text,
    extract_jd_text_async,
    NeedManualInput,
    JDSource,
)


def test_text_source_returns_content_directly():
    source = JDSource(type="text", content="我们在招聘高级工程师")
    result = extract_jd_text(source)
    assert result == "我们在招聘高级工程师"


def test_text_source_strips_whitespace():
    source = JDSource(type="text", content="  JD 内容  ")
    result = extract_jd_text(source)
    assert result == "JD 内容"


@pytest.mark.asyncio
async def test_url_source_fetch_success():
    source = JDSource(type="url", url="https://example.com/job")
    with patch("app.services.jd_extractor._fetch_url", new_callable=AsyncMock) as mock:
        mock.return_value = "工程师岗位要求"
        result = await extract_jd_text_async(source)
    assert result == "工程师岗位要求"


@pytest.mark.asyncio
async def test_url_source_fetch_failure_raises_need_manual_input():
    source = JDSource(type="url", url="https://linkedin.com/jobs/1234")
    with patch("app.services.jd_extractor._fetch_url", new_callable=AsyncMock) as mock:
        mock.return_value = None
        with pytest.raises(NeedManualInput):
            await extract_jd_text_async(source)


def test_file_source_pdf():
    source = JDSource(type="file", filename="jd.pdf", content_bytes=b"%PDF-1.4 fake")
    with patch("app.services.jd_extractor._parse_pdf", return_value="PDF JD 内容"):
        result = extract_jd_text(source)
    assert result == "PDF JD 内容"


def test_file_source_docx():
    source = JDSource(type="file", filename="jd.docx", content_bytes=b"fake docx")
    with patch("app.services.jd_extractor._parse_docx", return_value="Word JD 内容"):
        result = extract_jd_text(source)
    assert result == "Word JD 内容"
