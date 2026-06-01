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
from app.models.core import InterviewSession, User
from app.schemas.interview import CoachOpeningMessageResponse

log = get_logger("app.services.coach_opening")

COACH_OPENING_CACHE_KEY_TEMPLATE = "coach:opening:{user_id}"
COACH_OPENING_CACHE_TTL = 86400  # 24 小时

COACH_OPENING_SYSTEM_PROMPT = """
你是 AI 面试教练。根据用户真实的面试历史数据，生成个性化开场白。

【输入数据说明】
- practiced_roles：用户练过的岗位及场次，例如 {"AI Agent工程师": 2}
- recent_sessions：最近每场面试的详情，包含维度分（1-5分）、优点、待改进点
  - technical_depth：技术深度
  - quantified_results：量化成果
  - failure_tradeoffs：失败与取舍
  - structure：结构表达
  - improvements：该场面试的具体改进建议（LLM 原话）
  - highlights：该场面试做得好的地方
- common_issues：跨场次反复出现的问题标签及次数
- pass_rate：通过率（0.0-1.0）
- trend：分数趋势（improving/flat/declining）
- resume_text：用户的个人简历内容（如果已上传）

【生成规则】
greeting（1句）：
- 提到用户练了什么岗位、几场，语气简短直接，不说废话
- 如果是新用户（is_new=true）且有 resume_text，可以根据简历内容打招呼，如："我看过你的简历了，你在 [某项目/某公司] 的经历很亮眼，想聊聊吗？"
- 例："你练了 2 场 AI Agent 工程师，通过率 50%，继续。"
- 禁止："欢迎回来！今天我们继续关注你的面试表现，帮助你进一步提升技能。"

weakness_summary（1-2句）：
- 必须点出最突出的短板维度（找 recent_sessions 里分数最低的维度）
- 用具体分数说话，例："你的量化成果维度平均 2.1 分，是四个维度里最低的。"
- 新用户且有简历时，可以根据简历内容预估一个可能的挑战点，如："作为 [某岗位]，面试中经常会被问到 [某技术]，这是个不小的挑战。"
- 禁止使用：提升空间、规律、改进机会、加强能力、建议关注

evidence（1-2句）：
- 直接引用 recent_sessions 里的 improvements 原话或 common_issues 中的高频问题
- 说清楚是哪场出了什么问题，或哪个问题在几场里反复出现
- 如果是新用户，可以引用简历中的一段关键词作为引子
- 禁止编造输入中没有的数据，禁止重复 weakness_summary 的内容

focus_today（1句）：
- 格式：「今天重点练……，目标是……」
- 针对 weakness_summary 给出具体的练习方向，不能只说"练量化"，要说练什么类型的题/怎么练
- 例："今天重点练技术方案类题目，每个方案后面必须给出至少一个具体数字（延迟、吞吐、准确率等），目标是把量化分从 2 分拉到 3 分以上。"

【其他约束】
- 前端逐段渲染，每个字段必须是完整自然的中文句子，不要有多余标点或 Markdown
- 必须返回结构化 JSON，不要输出 JSON 以外的任何内容
- 新用户（is_new=true）且无简历：weakness_summary 和 evidence 返回 null，greeting 推荐岗位，focus_today 说明从哪里开始

返回格式：
{
  "greeting": "...",
  "weakness_summary": "...",
  "evidence": "...",
  "focus_today": "...",
  "cta_type": "new" | "returning"
}
""".strip()


class RecentSessionSummary(BaseModel):
    """单场面试的关键评价摘要，供 Coach 生成开场词时引用。"""

    role: str | None
    score: float | None
    pass_fail: str | None
    technical_depth: float | None
    quantified_results: float | None
    failure_tradeoffs: float | None
    structure: float | None
    improvements: list[str]
    highlights: list[str]


class CoachHistoryContext(BaseModel):
    """用于生成 Coach 开场词的历史指标上下文。"""

    session_count: int
    recent_scores: list[float]
    pass_rate: float
    common_issues: dict[str, int]
    trend: Literal["improving", "declining", "flat"]
    is_new: bool
    resume_text: str | None = None
    practiced_roles: dict[str, int]
    recent_sessions: list[RecentSessionSummary]


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


def _extract_report_dim(report: dict | None, key: str) -> float | None:
    """从 report_json 中安全提取维度分数。"""
    if not report:
        return None
    val = report.get(key)
    return float(val) if val is not None else None


def _extract_report_list(report: dict | None, key: str) -> list[str]:
    """从 report_json 中安全提取字符串列表字段。"""
    if not report:
        return []
    items = report.get(key, [])
    return [str(i) for i in items] if isinstance(items, list) else []


async def build_coach_history_context(
    db: AsyncSession, *, user_id: str
) -> CoachHistoryContext:
    """从用户已完成的历史 session 汇总场次、分数、通过率、常见问题和趋势。"""
    # 获取用户信息（含简历）
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

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

    role_counter: Counter[str] = Counter()
    for session in sessions:
        if session.target_role:
            role_counter[session.target_role] += 1

    recent_sessions: list[RecentSessionSummary] = []
    for session in sessions[:3]:
        report = session.report_json or {}
        recent_sessions.append(
            RecentSessionSummary(
                role=session.target_role,
                score=float(session.score) if session.score is not None else None,
                pass_fail=session.pass_fail,
                technical_depth=_extract_report_dim(report, "technical_depth"),
                quantified_results=_extract_report_dim(report, "quantified_results"),
                failure_tradeoffs=_extract_report_dim(report, "failure_tradeoffs"),
                structure=_extract_report_dim(report, "structure"),
                improvements=_extract_report_list(report, "improvements"),
                highlights=_extract_report_list(report, "highlights"),
            )
        )

    return CoachHistoryContext(
        session_count=len(sessions),
        recent_scores=recent_scores,
        pass_rate=pass_rate,
        common_issues=dict(issue_counter.most_common(5)),
        trend=_calculate_trend(recent_scores),
        is_new=len(sessions) == 0,
        resume_text=user.resume_text if user else None,
        practiced_roles=dict(role_counter),
        recent_sessions=recent_sessions,
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
    if context.is_new:
        return CoachOpeningMessageResponse(
            greeting="欢迎来到 AI 面试教练。先选择一个你想练习的岗位，我们会从一场模拟面试开始。",
            weakness_summary=None,
            evidence=None,
            focus_today="今天可以先从 AI Agent 工程师、后端工程师或前端工程师里选一个方向。",
            cta_type="new",
        )

    top_issue, issue_count = next(iter(context.common_issues.items()), ("技术细节不足", 0))

    role_summary = "、".join(
        f"{role} {count} 场" for role, count in list(context.practiced_roles.items())[:2]
    )
    greeting = f"你练了 {role_summary}，共 {context.session_count} 场，通过率 {round(context.pass_rate * 100)}%。"

    # 找最低维度分
    weakest_dim: str | None = None
    weakest_score: float = float("inf")
    dim_names = {
        "quantified_results": "量化成果",
        "technical_depth": "技术深度",
        "failure_tradeoffs": "失败与取舍",
        "structure": "结构表达",
    }
    for session in context.recent_sessions:
        for dim_key, dim_label in dim_names.items():
            val = getattr(session, dim_key)
            if val is not None and val < weakest_score:
                weakest_score = val
                weakest_dim = dim_label

    weakness_label = weakest_dim or f"「{top_issue}」"
    weakness_summary = (
        f"你的{weakness_label}是当前最薄弱的环节，"
        f"需要在回答中补充更具体的数据和结果。"
    )
    evidence = (
        f"「{top_issue}」在你过去 {context.session_count} 场中出现了 {issue_count} 次，"
        f"是反复出现的高频问题。"
    )
    focus_today = f"今天重点练{weakness_label}，每个技术方案后面至少给出一个具体数字（延迟、吞吐、准确率等）。"

    return CoachOpeningMessageResponse(
        greeting=greeting,
        weakness_summary=weakness_summary,
        evidence=evidence,
        focus_today=focus_today,
        cta_type="returning",
    )
