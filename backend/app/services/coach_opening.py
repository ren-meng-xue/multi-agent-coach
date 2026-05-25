"""生成 Coach 页面个性化开场词。"""
from collections import Counter
from typing import Literal

import redis.asyncio as redis
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.core import InterviewSession
from app.schemas.interview import CoachOpeningMessageResponse

log = get_logger("app.services.coach_opening")

COACH_OPENING_CACHE_KEY_TEMPLATE = "coach:opening:{user_id}"
COACH_OPENING_CACHE_TTL = 86400  # 24 小时

COACH_OPENING_SYSTEM_PROMPT = """
你是 AI 面试教练。根据用户的面试历史数据，生成个性化的开场白。

要求：
1. 如果是新用户（首次），推荐岗位选择。
2. 如果是老用户，weakness_summary 必须是一段可直接展示给用户的诊断文案，明确指出面试者最突出的不足或短板，语气像面试教练给诊断，不要像产品总结。
3. weakness_summary 必须使用「你在……方面不足 / 你缺少…… / 你的……不够具体」这类句式，明确说出缺什么。
4. evidence 必须是一段可直接展示给用户的证据文案，基于输入数据说明这个不足出现了多少次、影响了哪些场次或趋势；不要编造输入中没有的数据。
5. 禁止在 weakness_summary 和 evidence 中使用这些泛化表达：规律、改进机会、加强能力、提升空间、建议关注、频繁出现。
6. focus_today 必须是一段可直接展示给用户的训练安排，格式接近「今天重点练……」，并服务于补齐 weakness_summary 指出的不足。
7. 前端只会逐段渲染返回字段，不会再拼接业务句子；所以每个字段都必须是完整自然的中文句子。
8. 必须返回结构化 JSON，不要输出 Markdown，不要输出 JSON 之外的解释。

返回格式：
{
  "greeting": "...",
  "weakness_summary": "...",
  "evidence": "...",
  "focus_today": "...",
  "cta_type": "new" | "returning"
}
""".strip()


class CoachHistoryContext(BaseModel):
    """用于生成 Coach 开场词的历史指标上下文。"""

    session_count: int
    recent_scores: list[float]
    pass_rate: float
    common_issues: dict[str, int]
    trend: Literal["improving", "declining", "flat"]
    is_new: bool


async def get_coach_redis() -> redis.Redis:
    """获取 Redis 异步客户端。"""
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


async def invalidate_coach_opening_cache(user_id: str) -> None:
    """清除指定用户的 Coach 开场词缓存。"""
    cache_key = COACH_OPENING_CACHE_KEY_TEMPLATE.format(user_id=user_id)
    try:
        r = await get_coach_redis()
        await r.delete(cache_key)
        await r.close()
    except Exception as exc:
        log.warning("coach_opening_cache_invalidate_failed", user_id=user_id, error=str(exc))


def _coach_model() -> ChatOpenAI:
    """Create the coach LLM client from pydantic-settings."""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model_coach,
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
    )


async def build_coach_history_context(
    db: AsyncSession, *, user_id: str
) -> CoachHistoryContext:
    """从用户已完成的历史 session 汇总场次、分数、通过率、常见问题和趋势。"""
    result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "completed",
        )
        .order_by(InterviewSession.started_at.desc())
    )
    sessions = list(result.scalars())
    scored_sessions = [session for session in sessions if session.score is not None]
    recent_scores: list[float] = []
    for session in scored_sessions[:3]:
        if session.score is not None:
            recent_scores.append(float(session.score))
    passed_count = sum(1 for session in scored_sessions if session.pass_fail == "pass")
    pass_rate = passed_count / len(scored_sessions) if scored_sessions else 0.0

    issue_counter: Counter[str] = Counter()
    for session in scored_sessions:
        if session.key_issues:
            issue_counter.update(str(issue) for issue in session.key_issues)

    return CoachHistoryContext(
        session_count=len(sessions),
        recent_scores=recent_scores,
        pass_rate=pass_rate,
        common_issues=dict(issue_counter.most_common(5)),
        trend=_calculate_trend(recent_scores),
        is_new=len(sessions) == 0,
    )


def _calculate_trend(recent_scores: list[float]) -> Literal["improving", "declining", "flat"]:
    """根据最近分数判断趋势；列表按新到旧排序。"""
    if len(recent_scores) < 2:
        return "flat"
    delta = recent_scores[0] - recent_scores[-1]
    if delta >= 0.3:
        return "improving"
    if delta <= -0.3:
        return "declining"
    return "flat"


@retry(wait=wait_exponential(multiplier=1, min=1, max=4), stop=stop_after_attempt(3), reraise=True)
async def _generate_opening_from_llm(
    context: CoachHistoryContext,
) -> CoachOpeningMessageResponse:
    """Call the LLM with structured output so the frontend always receives JSON."""
    model = _coach_model().with_structured_output(CoachOpeningMessageResponse)
    output = await model.ainvoke(
        [
            SystemMessage(content=COACH_OPENING_SYSTEM_PROMPT),
            HumanMessage(content=context.model_dump_json()),
        ]
    )
    if isinstance(output, CoachOpeningMessageResponse):
        return output
    log.warning("coach_opening_unexpected_output", output=str(output))
    raise RuntimeError("unexpected coach opening output")


async def generate_coach_opening_message(
    db: AsyncSession, *, user_id: str
) -> CoachOpeningMessageResponse:
    """基于历史面试数据生成 Coach 页面开场词；优先从 Redis 缓存读取。"""
    cache_key = COACH_OPENING_CACHE_KEY_TEMPLATE.format(user_id=user_id)
    r = await get_coach_redis()

    try:
        # 1. 尝试从缓存读取
        cached_data = await r.get(cache_key)
        if cached_data:
            return CoachOpeningMessageResponse.model_validate_json(cached_data)

        # 2. 缓存未命中，执行常规逻辑
        context = await build_coach_history_context(db, user_id=user_id)
        try:
            response = await _generate_opening_from_llm(context)

            # 3. 写入缓存
            try:
                await r.setex(cache_key, COACH_OPENING_CACHE_TTL, response.model_dump_json())
            except Exception as exc:
                log.warning("coach_opening_cache_write_failed", user_id=user_id, error=str(exc))

            return response
        except Exception as exc:
            log.warning(
                "coach_opening_llm_failed",
                user_id=user_id,
                error=str(exc),
                session_count=context.session_count,
            )
            return _fallback_opening_message(context)
    except Exception as exc:
        log.warning("coach_opening_process_failed", user_id=user_id, error=str(exc))
        # 即使 Redis 读写挂了，也要保证能返回兜底，不影响页面加载
        context = await build_coach_history_context(db, user_id=user_id)
        return _fallback_opening_message(context)
    finally:
        await r.close()


def _fallback_opening_message(context: CoachHistoryContext) -> CoachOpeningMessageResponse:
    """LLM 不可用时仍返回可渲染结构，避免 Coach 页面空白。"""
    top_issue, issue_count = next(iter(context.common_issues.items()), ("技术细节不足", 0))
    if context.is_new:
        return CoachOpeningMessageResponse(
            greeting="欢迎来到 AI 面试教练。先选择一个你想练习的岗位，我们会从一场模拟面试开始。",
            weakness_summary=None,
            evidence=None,
            focus_today="今天可以先从 AI Agent 工程师、后端工程师或前端工程师里选一个方向。",
            cta_type="new",
        )
    return CoachOpeningMessageResponse(
        greeting="欢迎回来，今天继续把面试表达练扎实。",
        weakness_summary=f"你在「{top_issue}」方面还不够具体，需要把经历、动作和结果讲得更清楚。",
        evidence=f"这个短板在你过去 {context.session_count} 场面试中出现了 {issue_count} 场，是当前最需要优先处理的问题。",
        focus_today=f"今天重点练围绕「{top_issue}」补充更具体的项目证据、结果数据和复盘结论。",
        cta_type="returning",
    )
