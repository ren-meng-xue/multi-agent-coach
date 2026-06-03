# backend/app/api/v1/prepare.py
"""Prepare pipeline API endpoints."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prepare.graph import stream_prepare_events
from app.agents.prepare.state import PrepareState
from app.api.v1.auth import get_current_user_id
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.core import InterviewMessage, InterviewSession
from app.services.interview_turn import encode_prepare_trace_message, stream_interview_turn
from app.services.jd_extractor import JDSource, NeedManualInput, extract_jd_text_async

router = APIRouter()
log = get_logger("app.api.v1.prepare")


async def _sse_format(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    try:
        async for ev in events:
            event_name = ev.get("event", "message")
            data = ev.get("data", {})
            yield f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    except asyncio.CancelledError:
        log.info("prepare_stream_cancelled")
        raise
    except Exception as exc:
        log.error("prepare_stream_failed", error=str(exc), exc_info=True)
        error_payload = {
            "message": "准备流水线失败，请直接进入面试或稍后重试。",
            "code": "prepare_stream_failed",
        }
        yield f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"


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
            payload = {"message": err_msg, "code": "need_manual_input"}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")
    except Exception as exc:
        log.error("jd_extract_failed", error=str(exc))
        err_msg = "JD 提取失败，请手动粘贴 JD 文本后重试。"

        async def _generic_err():
            payload = {"message": err_msg, "code": "jd_extract_failed"}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        return StreamingResponse(_generic_err(), media_type="text/event-stream")

    session_id = str(uuid.uuid4())

    state: PrepareState = {
        "session_id": session_id,
        "user_id": user_id,
        "user_direction": user_direction or None,
        "user_background": user_background or None,
        "jd_raw": jd_raw,
        "weak_areas": [],
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

    if session_id:
        try:
            from app.services.coach_opening import get_coach_redis
            r = await get_coach_redis()
            cached = await r.get(f"prepare:state:{user_id}:{session_id}")
            if cached:
                data = json.loads(cached)
                weak_areas_list = data.get("weak_areas", [])
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
    }

    return StreamingResponse(
        _sse_format(stream_prepare_events(state)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# 哪些 service-side 事件需要透传给前端（加 turn_ 前缀）。
# service 自己的 done 单独吞掉、由本 generator 自行合成最终 turn_done，避免双 done 混淆前端时序。
_TURN_FORWARD_EVENTS = frozenset({
    "node_start", "node_token", "node_done", "delta", "state", "report",
})


def _empty_prepare_trace() -> dict:
    return {
        "status": "running",
        "nodes": [],
        "questions": [],
        "summary": "",
        "direction": None,
    }


def _apply_prepare_trace_event(payload: dict, ev: dict) -> None:
    event = ev.get("event")
    data = ev.get("data", {}) or {}
    node_id = data.get("node")

    if event == "node_start" and node_id:
        nodes = payload.setdefault("nodes", [])
        if any(node.get("id") == node_id for node in nodes):
            for node in nodes:
                if node.get("id") == node_id:
                    node["status"] = "running"
            return
        nodes.append({
            "id": node_id,
            "label": data.get("label") or node_id,
            "title": data.get("title") or node_id,
            "status": "running",
            "tokens": "",
        })
        return

    if event == "node_token" and node_id:
        for node in payload.setdefault("nodes", []):
            if node.get("id") == node_id:
                node["tokens"] = f"{node.get('tokens', '')}{data.get('text', '')}"
                break
        return

    if event == "node_done" and node_id:
        for node in payload.setdefault("nodes", []):
            if node.get("id") == node_id:
                node["status"] = "done"
                if data.get("elapsed_ms") is not None:
                    node["elapsedMs"] = data.get("elapsed_ms")
                break
        return

    if event == "done":
        payload["status"] = "done"
        payload["questions"] = data.get("prepared_questions", []) or []
        payload["summary"] = data.get("summary", "") or ""
        payload["direction"] = data.get("direction")
        payload["jdContext"] = data.get("jd_context")
        payload["jobIntel"] = data.get("job_intel")


async def _persist_prepare_trace(
    db: AsyncSession,
    *,
    user_id: str,
    payload: dict,
) -> None:
    result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "in_progress",
        )
        .order_by(InterviewSession.started_at.desc())
        .limit(1)
    )
    active = result.scalar_one_or_none()
    if active is None:
        return

    db.add(
        InterviewMessage(
            session_id=active.id,
            role="system",
            content=encode_prepare_trace_message(payload),
        )
    )
    await db.commit()


async def stream_prepare_and_launch(
    state: PrepareState,
    *,
    db: AsyncSession,
) -> AsyncIterator[dict]:
    """Prepare + interview 开场一体化 SSE generator。

    事件时序：
      prepare 阶段事件（node_start / node_token / node_done / ... / done）
      → node_start{launch} → node_done{launch} → phase_change{turn_id}
      → turn_* 面试事件 → turn_done
    need_direction=True 时在 prepare 阶段结束后直接返回，不接续 launch / turn。
    """
    prepared_questions: list[dict] = []
    jd_context: dict | None = None
    job_intel: dict | None = None
    need_direction = False
    prepare_trace = _empty_prepare_trace()

    # Phase 1: 透传 prepare 流
    async for ev in stream_prepare_events(state):
        _apply_prepare_trace_event(prepare_trace, ev)
        yield ev
        evt = ev.get("event", "")
        if evt == "done":
            data = ev.get("data", {})
            prepared_questions = data.get("prepared_questions", []) or []
            jd_context = data.get("jd_context")
            job_intel = data.get("job_intel")
        if evt == "node_done" and ev.get("data", {}).get("need_direction"):
            need_direction = True

    if need_direction:
        return

    await _persist_prepare_trace(db, user_id=state["user_id"], payload=prepare_trace)

    # Phase 2: 合成 "launch" 节点 + phase_change
    turn_id = str(uuid.uuid4())
    yield {"event": "node_start", "data": {"node": "launch", "label": "进入面试"}}
    yield {"event": "node_done", "data": {"node": "launch"}}
    yield {"event": "phase_change", "data": {"turn_id": turn_id}}

    # Phase 3: 面试 turn 事件加 turn_ 前缀；吞掉 service 的 done，自行合成 turn_done。
    async for turn_ev in stream_interview_turn(
        "__START__",
        user_id=state["user_id"],
        db=db,
        prepared_questions=prepared_questions or None,
        jd_context=jd_context,
        job_intel=job_intel,
    ):
        turn_event = turn_ev.get("event", "")
        if turn_event == "done":
            break
        if turn_event in _TURN_FORWARD_EVENTS:
            yield {"event": f"turn_{turn_event}", "data": turn_ev.get("data", {})}
    yield {"event": "turn_done", "data": {}}


@router.post("/prepare/launch")
async def prepare_launch(
    user_direction: str = Form(""),
    user_background: str = Form(""),
    jd_text: str = Form(""),
    jd_url: str = Form(""),
    jd_file: UploadFile | None = File(None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """准备 + 面试开场一体化端点：prepare pipeline 完成后自动接续 __START__ 轮。"""
    content_bytes = b""
    if jd_file and jd_file.filename:
        filename_lower = jd_file.filename.lower()
        if not (
            filename_lower.endswith(".pdf")
            or filename_lower.endswith(".docx")
            or filename_lower.endswith(".doc")
        ):
            raise HTTPException(status_code=400, detail="只支持 PDF 或 DOCX 文件")
        ALLOWED_TYPES = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }
        if jd_file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="只支持 PDF 或 DOCX 文件")
        MAX_SIZE = 10 * 1024 * 1024
        content_bytes = await jd_file.read(MAX_SIZE + 1)
        if len(content_bytes) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="文件大小不能超过 10MB")

    jd_raw: str | None = None
    try:
        if jd_text.strip():
            jd_raw = jd_text.strip()
        elif jd_file is not None and jd_file.filename:
            source = JDSource(type="file", filename=jd_file.filename, content_bytes=content_bytes)
            jd_raw = await extract_jd_text_async(source)
        elif jd_url.strip():
            source = JDSource(type="url", url=jd_url.strip())
            jd_raw = await extract_jd_text_async(source)
    except NeedManualInput as exc:
        err_msg = str(exc)

        async def _err():
            payload = {"message": err_msg, "code": "need_manual_input"}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

        return StreamingResponse(_err(), media_type="text/event-stream")
    except Exception as exc:
        log.error("jd_extract_failed", error=str(exc))
        err_msg = "JD 提取失败，请手动粘贴 JD 文本后重试。"

        async def _generic_err():
            payload = {"message": err_msg, "code": "jd_extract_failed"}
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

        return StreamingResponse(_generic_err(), media_type="text/event-stream")

    session_id = str(uuid.uuid4())

    state: PrepareState = {
        "session_id": session_id,
        "user_id": user_id,
        "user_direction": user_direction or None,
        "user_background": user_background or None,
        "jd_raw": jd_raw,
        "weak_areas": [],
    }

    return StreamingResponse(
        _sse_format(stream_prepare_and_launch(state, db=db)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
