# backend/app/api/v1/prepare.py
"""Prepare pipeline API endpoints."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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
    # [C2] 文件上传校验
    content_bytes = b""
    if jd_file and jd_file.filename:
        # 后缀校验
        filename_lower = jd_file.filename.lower()
        if not (filename_lower.endswith(".pdf") or filename_lower.endswith(".docx") or filename_lower.endswith(".doc")):
            raise HTTPException(status_code=400, detail="只支持 PDF 或 DOCX 文件")

        # 类型校验
        ALLOWED_TYPES = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }
        if jd_file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="只支持 PDF 或 DOCX 文件")
        
        # 大小校验 (10MB)
        # 注意：此处的文件大小业务层校验主要是作为兜底判断。
        # 真正防止 multipart parser 在解析时把超大文件写入 spool 的第一层物理拦截防护，
        # 已由 app/main.py 中的 ContentSizeLimitMiddleware 全局中间件在最外层完成。
        MAX_SIZE = 10 * 1024 * 1024
        content_bytes = await jd_file.read(MAX_SIZE + 1)
        if len(content_bytes) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="文件大小不能超过 10MB")
    
    # 提取 JD 文本
    jd_raw: str | None = None
    try:
        if jd_text.strip():
            jd_raw = jd_text.strip()
        elif jd_file is not None and jd_file.filename:
            # 零二次读取，直接使用前面已读入的 content_bytes
            source = JDSource(type="file", filename=jd_file.filename, content_bytes=content_bytes)
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

    import uuid
    session_id = str(uuid.uuid4())

    state: PrepareState = {
        "session_id": session_id,
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
    jd_text: str = Form(""),
    session_id: str = Form(""),
    user_id: str = Depends(get_current_user_id),
):
    """用户回答方向后，继续准备流水线（need_direction=True 场景）。"""
    weak_areas_list = []
    star_stories_list = []

    if session_id:
        try:
            from app.services.coach_opening import get_coach_redis
            r = await get_coach_redis()
            cached = await r.get(f"prepare:state:{user_id}:{session_id}")
            if cached:
                data = json.loads(cached)
                weak_areas_list = data.get("weak_areas", [])
                star_stories_list = data.get("star_stories", [])
                log.info("prepare_state_restored", session_id=session_id)
        except Exception as exc:
            log.warning("prepare_state_restore_failed", session_id=session_id, error=str(exc))

    state: PrepareState = {
        "session_id": session_id,
        "user_id": user_id,
        "user_direction": direction,
        "user_background": user_background or None,
        "jd_raw": jd_text.strip() or None,
        "weak_areas": weak_areas_list,
        "star_stories": star_stories_list,
    }

    return StreamingResponse(
        _sse_format(stream_prepare_events(state)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

