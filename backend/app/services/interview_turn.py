"""统一面试入口：按 Clerk user_id 管理内部面试 run，并持久化消息。"""
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.interviewer.graph import stream_interviewer_turn_events
from app.agents.interviewer.state import InterviewState
from app.core.logging import get_logger
from app.models.core import InterviewMessage, InterviewSession, User
from app.services.coach_opening import invalidate_coach_opening_cache

log = get_logger("app.services.interview_turn")
ABANDON_AFTER = timedelta(hours=24)


def _placeholder_email(user_id: str) -> str:
    """为尚未同步邮箱的 Clerk 用户生成稳定占位邮箱，避免外键写入失败。"""
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
    return f"{digest}@clerk.local"


async def ensure_user_exists(db: AsyncSession, *, user_id: str) -> User:
    """确保 users 表存在当前 Clerk user_id。

    当前鉴权依赖只返回 sub，不含邮箱；真实邮箱后续应由 Clerk webhook 或用户同步流程更新。
    """
    user = await db.get(User, user_id)
    if user is not None:
        return user

    user = User(id=user_id, email=_placeholder_email(user_id))
    db.add(user)
    await db.flush()
    return user


async def get_or_create_active_session(
    db: AsyncSession, *, user_id: str
) -> tuple[InterviewSession, bool]:
    """返回当前用户的内部进行中面试 run；没有则自动创建。

    返回的 bool 表示这是否是用户第一次拥有面试 run，用于 opening 阶段区分新老用户。
    """
    await ensure_user_exists(db, user_id=user_id)

    total_result = await db.execute(
        select(func.count()).select_from(InterviewSession).where(InterviewSession.user_id == user_id)
    )
    is_first_time = total_result.scalar_one() == 0

    active_result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "in_progress",
        )
        .order_by(InterviewSession.started_at.desc())
        .limit(1)
    )
    active = active_result.scalar_one_or_none()
    if active is not None:
        if await _is_stale_active_session(db, active):
            active.status = "abandoned"
            await db.flush()
        else:
            return active, is_first_time

    session = InterviewSession(user_id=user_id)
    db.add(session)
    await db.flush()
    return session, is_first_time


async def _is_stale_active_session(db: AsyncSession, session: InterviewSession) -> bool:
    """Return true when an in-progress run has no activity for the abandoned timeout."""
    last_message_result = await db.execute(
        select(func.max(InterviewMessage.created_at)).where(
            InterviewMessage.session_id == session.id
        )
    )
    last_activity = last_message_result.scalar_one_or_none() or session.started_at
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=UTC)
    return datetime.now(UTC) - last_activity >= ABANDON_AFTER


def _to_langchain_message(message: InterviewMessage) -> BaseMessage | None:
    """Convert a persisted interview message to a LangChain message."""
    if message.role == "user":
        return HumanMessage(content=message.content)
    if message.role == "assistant":
        return AIMessage(content=message.content)
    if message.role == "system":
        return SystemMessage(content=message.content)
    return None


async def _load_session_messages(
    db: AsyncSession, *, session_id: UUID, current_message: str
) -> list[BaseMessage]:
    """Load the current run history and append the latest user message."""
    result = await db.execute(
        select(InterviewMessage)
        .where(InterviewMessage.session_id == session_id)
        .order_by(InterviewMessage.created_at)
    )
    messages: list[BaseMessage] = []
    for stored_message in result.scalars():
        converted = _to_langchain_message(stored_message)
        if converted is not None:
            messages.append(converted)
    messages.append(HumanMessage(content=current_message))
    return messages


def _build_state(
    *,
    session: InterviewSession,
    user_id: str,
    is_first_time: bool,
    messages: list[BaseMessage],
) -> InterviewState:
    return {
        "session_id": str(session.id),
        "user_id": user_id,
        "is_first_time": is_first_time,
        "target_role": session.target_role or "",
        "target_company": session.target_company or "",
        "user_background": session.user_background or "",
        "messages": messages,
        "stage": cast(Any, session.stage),
        "question_count": session.question_count,
        "total_questions": session.total_questions,
        "followup_count": session.followup_count,
        "max_followups": 2,
    }


async def get_user_interview_context(db: AsyncSession, *, user_id: str) -> dict:
    """返回 Coach 页面所需的用户上下文：优先使用 User 表持久化配置，回退至最近 session。"""
    user = await ensure_user_exists(db, user_id=user_id)
    
    completed_count_result = await db.execute(
        select(func.count())
        .select_from(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "completed",
        )
    )
    completed_count = completed_count_result.scalar_one()

    # 基础返回结构
    ctx = {
        "is_returning": completed_count > 0,
        "target_role": user.target_role,
        "work_years": user.work_years,
        "target_company": None,
        "user_background": None,
        "session_count": completed_count,
    }

    # 如果 User 表没设岗位，尝试从最近 session 捞
    if not ctx["target_role"]:
        latest_result = await db.execute(
            select(InterviewSession)
            .where(
                InterviewSession.user_id == user_id,
                InterviewSession.target_role.is_not(None),
            )
            .order_by(InterviewSession.started_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()
        if latest:
            ctx["target_role"] = latest.target_role
            ctx["target_company"] = latest.target_company
            ctx["user_background"] = latest.user_background

    return ctx


async def reset_interview_session(
    db: AsyncSession,
    *,
    user_id: str,
    target_role: str | None = None,
    user_background: str | None = None,
) -> None:
    """放弃当前用户所有进行中的面试 session。

    若携带 target_role，则在 abandon 旧 session 后立即创建预置岗位信息的新 session，
    供 LangGraph opening 节点直接跳过重新收集。
    """
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "in_progress",
        )
    )
    sessions = result.scalars().all()
    for session in sessions:
        session.status = "abandoned"
        log.info("interview_session_reset", user_id=user_id, session_id=str(session.id))

    if target_role:
        await ensure_user_exists(db, user_id=user_id)
        new_session = InterviewSession(
            user_id=user_id,
            target_role=target_role,
            user_background=user_background,
        )
        db.add(new_session)
        log.info(
            "interview_session_preseeded",
            user_id=user_id,
            target_role=target_role,
        )

    if sessions or target_role:
        await db.commit()


async def get_active_interview_session(
    db: AsyncSession,
    *,
    user_id: str,
) -> dict:
    """获取当前处于进行中（in_progress）的活动会话及历史消息记录。"""
    await ensure_user_exists(db, user_id=user_id)

    active_result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "in_progress",
        )
        .order_by(InterviewSession.started_at.desc())
        .limit(1)
    )
    active = active_result.scalar_one_or_none()

    if active is not None:
        if await _is_stale_active_session(db, active):
            active.status = "abandoned"
            await db.commit()
            return {}

        # 加载历史消息记录
        msg_result = await db.execute(
            select(InterviewMessage)
            .where(InterviewMessage.session_id == active.id)
            .order_by(InterviewMessage.created_at)
        )
        stored_messages = msg_result.scalars().all()

        messages = []
        for m in stored_messages:
            # 过滤只加载 user 和 assistant 的对话，避免把 system 或 trace 垃圾消息带入前端
            if m.role in ("user", "assistant"):
                messages.append({
                    "role": m.role,
                    "content": m.content,
                })

        return {
            "session_id": str(active.id),
            "target_role": active.target_role or "",
            "target_company": active.target_company or "",
            "user_background": active.user_background or "",
            "stage": active.stage,
            "question_count": active.question_count,
            "total_questions": active.total_questions,
            "followup_count": active.followup_count,
            "messages": messages,
            "report": active.report_json,
        }

    return {}


async def stream_interview_turn(
    message: str,
    *,
    user_id: str,
    db: AsyncSession,
    prepared_questions: list[dict[str, Any]] | None = None,
    jd_context: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """处理统一入口的一轮对话，流式返回 SSE 事件数据。

    入口、用户归属、内部 run 与消息持久化由 service 负责；面试流程推进由 LangGraph 负责。
    """
    session, is_first_time = await get_or_create_active_session(db, user_id=user_id)
    history = await _load_session_messages(db, session_id=session.id, current_message=message)
    state = _build_state(
        session=session,
        user_id=user_id,
        is_first_time=is_first_time,
        messages=history,
    )
    if is_first_time:
        if prepared_questions:
            state["prepared_questions"] = prepared_questions
        if jd_context:
            state["jd_context"] = jd_context

    assistant_chunks: list[str] = []
    output: InterviewState | None = None
    async for graph_event in stream_interviewer_turn_events(state):
        evt = graph_event["event"]
        data = graph_event["data"]
        if evt == "token":
            text = data.get("text", "")
            if text:
                assistant_chunks.append(text)
                yield {"event": "delta", "data": {"text": text}}
            continue
        if evt in ("node_start", "node_token", "node_done"):
            yield {"event": evt, "data": data}
            continue
        if evt == "final":
            output = data

    if output is None:
        log.warning("interview_turn_missing_graph_output", user_id=user_id, session_id=str(session.id))
        raise RuntimeError("missing graph output")

    assistant_content = output.get("assistant_message", "").strip()
    if not assistant_content:
        log.warning("interview_turn_empty_assistant_reply", user_id=user_id, session_id=str(session.id))
        raise RuntimeError("empty assistant reply")

    session.stage = output.get("stage", session.stage)
    session.target_role = output.get("target_role", session.target_role)
    session.target_company = output.get("target_company", session.target_company)
    session.user_background = output.get("user_background", session.user_background)
    session.question_count = output.get("question_count", session.question_count)
    session.followup_count = output.get("followup_count", session.followup_count)
    report_data = output.get("report")
    if session.stage == "closing":
        session.status = "completed"
        session.completed_at = datetime.now(UTC)
        # 面试结束，标记 Coach 缓存失效，确保下次进入生成最新诊断
        await invalidate_coach_opening_cache(user_id=user_id)
        if isinstance(report_data, dict) and report_data:
            score = float(report_data.get("overall_score", 0))
            improvements = report_data.get("improvements", [])
            session.score = score
            
            # 细化通过逻辑：7分通过，6分待定，6分以下未过
            if score >= 7.0:
                session.pass_fail = "pass"
            elif score >= 6.0:
                session.pass_fail = "partial"
            else:
                session.pass_fail = "fail"
                
            session.key_issues = improvements if isinstance(improvements, list) else []
            session.report_json = report_data

    yield {
        "event": "state",
        "data": {
            "stage": session.stage,
            "question_count": session.question_count,
            "total_questions": session.total_questions,
        },
    }
    if not assistant_chunks:
        yield {"event": "delta", "data": {"text": assistant_content}}

    db.add_all(
        [
            InterviewMessage(
                session_id=session.id,
                role="user",
                content=message,
                question_number=session.question_count or None,
            ),
            InterviewMessage(
                session_id=session.id,
                role="assistant",
                content=assistant_content,
                question_number=session.question_count or None,
            ),
        ]
    )
    await db.commit()

    if session.stage == "closing" and report_data:
        yield {"event": "report", "data": report_data}

    yield {"event": "done", "data": {}}
