"""面试对话接口：以 SSE 流式返回面试官回复。"""
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.auth import get_current_user_id
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.interview import (
    ChatRequest,
    InterviewHistoryResponse,
    ResetRequest,
    TurnRequest,
    UserContextResponse,
)
from app.services.interview_chat import stream_interview_reply
from app.services.interview_history import get_interview_history
from app.services.interview_turn import (
    get_user_interview_context,
    reset_interview_session,
    stream_interview_turn,
)

router = APIRouter(prefix="/interview")
log = get_logger("app.api.v1.interview")


@router.post("/chat")
async def chat(
    req: ChatRequest, user_id: str = Depends(get_current_user_id)
) -> EventSourceResponse:
    """面试官单轮流式问答：逐段以 delta 事件下发，正常结束发 done，失败发 error。

    鉴权/入参校验失败（401/422）由全局异常处理器以统一 Response 返回，不进入此流。
    """

    async def event_gen() -> AsyncIterator[dict[str, str]]:
        try:
            async for text in stream_interview_reply(req.messages, user_id=user_id):
                yield {"event": "delta", "data": json.dumps({"text": text}, ensure_ascii=False)}
            yield {"event": "done", "data": "{}"}
        except Exception:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": "AI 暂时无法响应，请稍后重试"}, ensure_ascii=False
                ),
            }

    return EventSourceResponse(
        event_gen(),
        headers={
            "Deprecation": "true",
            "Link": '</api/v1/interview/turn>; rel="successor-version"',
            "X-Deprecated-Endpoint": "Use /api/v1/interview/turn",
        },
    )


@router.post("/turn")
async def turn(
    req: TurnRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """统一面试入口：前端只传本轮 message，后端按 Clerk user_id 管内部 run。"""

    async def event_gen() -> AsyncIterator[dict[str, str]]:
        try:
            async for event in stream_interview_turn(
                req.message,
                user_id=user_id,
                db=db,
                prepared_questions=req.prepared_questions,
                jd_context=req.jd_context,
            ):
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"], ensure_ascii=False),
                }
        except Exception as exc:
            log.error("interview_turn_failed", error=str(exc), exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": "AI 暂时无法响应，请稍后重试"}, ensure_ascii=False
                ),
            }

    return EventSourceResponse(event_gen())


@router.get("/context", response_model=UserContextResponse)
async def get_context(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserContextResponse:
    """返回 Coach 页面所需的用户上下文：判断新老用户、展示历史岗位信息。"""
    data = await get_user_interview_context(db, user_id=user_id)
    return UserContextResponse(**data)


@router.post("/reset")
async def reset(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    req: ResetRequest | None = None,
) -> dict:
    """放弃当前进行中的面试；可携带 Coach 收集的岗位上下文预建新 session。"""
    await reset_interview_session(
        db,
        user_id=user_id,
        target_role=req.target_role if req else None,
        user_background=req.user_background if req else None,
    )
    return {"status": "ok"}


@router.get("/history", response_model=InterviewHistoryResponse)
async def get_history(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    limit: int = 10,
) -> InterviewHistoryResponse:
    """获取用户的面试历史记录。"""
    return await get_interview_history(db, user_id=user_id, limit=limit)
