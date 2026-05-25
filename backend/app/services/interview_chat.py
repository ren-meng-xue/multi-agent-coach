"""面试官单轮流式问答：封装 OpenAI 流式调用，含超时、重试与失败日志。"""
from collections.abc import AsyncIterator
from typing import cast

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AsyncStream,
    InternalServerError,
    RateLimitError,
)
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.interview import ChatMessage

log = get_logger("app.services.interview_chat")
_client: AsyncOpenAI | None = None

# 面试官 system prompt：一次只问一个问题，专业克制，不替候选人作答
INTERVIEWER_SYSTEM_PROMPT = (
    "你是一位资深技术面试官，正在对候选人进行中文模拟面试。"
    "请根据候选人最新的回答，提出有针对性的面试问题或追问，一次只问一个问题，"
    "语气专业、简洁、克制。不要替候选人作答，也不要长篇大论地点评。"
)

# 仅这些"建流前"的瞬时错误可安全重试；一旦开始读取流就不能重试，否则会重复输出
_RETRYABLE = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


def _get_client() -> AsyncOpenAI:
    """返回可复用的 OpenAI 异步客户端，避免每请求重复建连接池。"""
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    _client = AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.llm_timeout_seconds,
    )
    return _client


async def close_client() -> None:
    """应用关闭时释放 OpenAI 底层 httpx 连接池。"""
    global _client
    if _client is None:
        return

    await _client.close()
    _client = None


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    reraise=True,
)
async def _create_stream(
    client: AsyncOpenAI, messages: list[ChatCompletionMessageParam]
) -> AsyncStream[ChatCompletionChunk]:
    """建立 OpenAI 流式响应。

    仅此步骤纳入重试——开始读取流之后再重试会重复已输出的内容，
    因此迭代阶段刻意排除在重试范围之外。
    """
    return await client.chat.completions.create(
        model=get_settings().openai_model_chat,
        messages=messages,
        stream=True,
    )


async def stream_interview_reply(
    messages: list[ChatMessage], *, user_id: str = ""
) -> AsyncIterator[str]:
    """以面试官身份对全量历史生成流式回复，逐段 yield 文本增量。

    失败处理：建流阶段重试耗尽、或迭代阶段断流，都会记 error 日志并向上抛出，
    由路由层转成 SSE error 事件返回给前端（绝不静默吞异常）。
    """
    client = _get_client()
    payload: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": INTERVIEWER_SYSTEM_PROMPT},
        *(cast(ChatCompletionMessageParam, m.model_dump()) for m in messages),
    ]

    try:
        stream = await _create_stream(client, payload)
    except Exception as exc:
        log.error("interview_llm_create_failed", user_id=user_id, error=str(exc))
        raise

    try:
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as exc:
        log.error("interview_llm_stream_failed", user_id=user_id, error=str(exc))
        raise
