# backend/app/api/v1/prepare.py
"""Prepare pipeline API endpoints."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.agents.prepare.graph import stream_prepare_events
from app.agents.prepare.state import PrepareState
from app.api.v1.auth import get_current_user_id
from app.core.logging import get_logger
from app.services.jd_extractor import JDSource, NeedManualInput, extract_jd_text_async

router = APIRouter()
log = get_logger("app.api.v1.prepare")


async def _sse_format(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    try:
        async for ev in events:
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
    except Exception as exc:
        log.error("prepare_stream_failed", error=str(exc), exc_info=True)
        error_event = {
            "event": "error",
            "data": {
                "message": "准备流水线失败，请直接进入面试或稍后重试。",
                "code": "prepare_stream_failed",
            },
        }
        yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"


@router.post("/prepare/start")
async def prepare_start(
    user_direction: str = Form(""),
    user_background: str = Form(""),
    jd_text: str = Form(""),
    jd_url: str = Form(""),
    jd_file: UploadFile | None = File(None),
    user_id: str = Depends(get_current_user_id),
):
    """启动准备流水线，返回 SSE 流。"""
    # 提取 JD 文本
    jd_raw: str | None = None
    try:
        if jd_text.strip():
            jd_raw = jd_text.strip()
        elif jd_file is not None and jd_file.filename:
            content = await jd_file.read()
            source = JDSource(type="file", filename=jd_file.filename, content_bytes=content)
            jd_raw = await extract_jd_text_async(source)
        elif jd_url.strip():
            source = JDSource(type="url", url=jd_url.strip())
            jd_raw = await extract_jd_text_async(source)
    except NeedManualInput as exc:
        err_msg = str(exc)

        async def _err():
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': err_msg, 'code': 'need_manual_input'}}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")
    except Exception as exc:
        log.error("jd_extract_failed", error=str(exc))
        err_msg = "JD 提取失败，请手动粘贴 JD 文本后重试。"

        async def _generic_err():
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': err_msg, 'code': 'jd_extract_failed'}}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_generic_err(), media_type="text/event-stream")

    state: PrepareState = {
        "user_id": user_id,
        "user_direction": user_direction or None,
        "user_background": user_background or None,
        "jd_raw": jd_raw,
        "weak_areas": [],
        "star_stories": [],
    }

    return StreamingResponse(
        _sse_format(stream_prepare_events(state)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/prepare/resume")
async def prepare_resume(
    direction: str = Form(...),
    user_background: str = Form(""),
    user_id: str = Depends(get_current_user_id),
):
    """用户回答方向后，继续准备流水线（need_direction=True 场景）。"""
    state: PrepareState = {
        "user_id": user_id,
        "user_direction": direction,
        "user_background": user_background or None,
        "jd_raw": None,
        "weak_areas": [],
        "star_stories": [],
        "need_direction": False,
    }
    return StreamingResponse(
        _sse_format(stream_prepare_events(state)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
