"""面试对话接口：以 SSE 流式返回面试官回复。"""
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.auth import get_current_user_id
from app.schemas.interview import ChatRequest
from app.services.interview_chat import stream_interview_reply

router = APIRouter(prefix="/interview")


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
            # service 层已记 error 日志，这里转成用户可见的 error 事件（绝不静默吞）
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": "AI 暂时无法响应，请稍后重试"}, ensure_ascii=False
                ),
            }

    return EventSourceResponse(event_gen())
