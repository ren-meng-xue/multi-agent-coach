"""统一面试入口 service：按 Clerk user_id 管理内部面试 run。"""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.core import InterviewMessage, InterviewSession, User
from app.services.interview_turn import (
    get_or_create_active_session,
    reset_interview_session,
    stream_interview_turn,
)


@pytest.mark.asyncio
async def test_get_or_create_active_session_creates_user_and_run(db):
    """没有历史时，按 Clerk user_id 自动创建用户占位记录和内部 run。"""
    user_id = f"user_turn_new_{uuid4().hex}"
    session, is_first_time = await get_or_create_active_session(db, user_id=user_id)
    await db.flush()

    assert is_first_time is True
    assert session.user_id == user_id
    assert session.status == "in_progress"

    user = await db.get(User, user_id)
    assert user is not None


@pytest.mark.asyncio
async def test_get_or_create_active_session_reuses_active_run(db):
    """同一用户已有进行中 run 时必须复用，避免前端感知 session。"""
    user_id = f"user_turn_reuse_{uuid4().hex}"
    first, _ = await get_or_create_active_session(db, user_id=user_id)
    second, is_first_time = await get_or_create_active_session(db, user_id=user_id)

    assert second.id == first.id
    assert is_first_time is False


@pytest.mark.asyncio
async def test_get_or_create_active_session_abandons_stale_active_run(db):
    """旧 run 超过 24 小时无活动时，新请求前标记 abandoned 并创建新 run。"""
    user_id = f"user_turn_stale_{uuid4().hex}"
    old_started_at = datetime.now(UTC) - timedelta(hours=25)
    await get_or_create_active_session(db, user_id=user_id)
    result = await db.execute(select(InterviewSession).where(InterviewSession.user_id == user_id))
    old_session = result.scalar_one()
    old_session.started_at = old_started_at
    await db.flush()

    new_session, is_first_time = await get_or_create_active_session(db, user_id=user_id)

    assert new_session.id != old_session.id
    assert old_session.status == "abandoned"
    assert new_session.status == "in_progress"
    assert is_first_time is False


@pytest.mark.asyncio
async def test_stream_interview_turn_persists_user_and_assistant_messages(db, monkeypatch):
    """统一入口完成一轮后，写入本轮 user + assistant 消息。"""

    async def fake_graph_events(state):
        yield {"event": "token", "data": {"text": "第一题，"}}
        yield {"event": "token", "data": {"text": "请介绍你的项目。"}}
        yield {
            "event": "final",
            "data": {
                **state,
                "stage": "interview",
                "target_role": "AI Agent 工程师",
                "target_company": "大厂",
                "user_background": "多 Agent 面试教练项目",
                "question_count": 1,
                "followup_count": 0,
                "assistant_message": "第一题，请介绍你的项目。",
            },
        }

    monkeypatch.setattr("app.services.interview_turn.stream_interviewer_turn_events", fake_graph_events)
    user_id = f"user_turn_stream_{uuid4().hex}"

    events = [
        event
        async for event in stream_interview_turn(
            "我想练 AI Agent 工程师",
            user_id=user_id,
            db=db,
        )
    ]

    assert [event["event"] for event in events] == ["delta", "delta", "state", "done"]
    assert [event["data"]["text"] for event in events[:2]] == ["第一题，", "请介绍你的项目。"]

    session_result = await db.execute(
        select(InterviewSession).where(InterviewSession.user_id == user_id)
    )
    session = session_result.scalar_one()
    message_result = await db.execute(
        select(InterviewMessage)
        .where(InterviewMessage.session_id == session.id)
        .order_by(InterviewMessage.created_at)
    )
    messages = message_result.scalars().all()

    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "我想练 AI Agent 工程师"
    assert messages[1].content == "第一题，请介绍你的项目。"
    assert session.stage == "interview"
    assert session.target_role == "AI Agent 工程师"
    assert session.target_company == "大厂"
    assert session.user_background == "多 Agent 面试教练项目"
    assert session.question_count == 1


@pytest.mark.asyncio
async def test_stream_interview_turn_raises_on_empty_assistant_reply(db, monkeypatch):
    """图输出 assistant_message 为空白时，service 层应抛出 RuntimeError 而非静默失败。"""

    async def fake_graph_events(state):
        # 只返回空白 message 的 final 事件，模拟图异常输出
        yield {"event": "final", "data": {**state, "assistant_message": "   "}}

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events", fake_graph_events
    )
    user_id = f"user_turn_empty_{uuid4().hex}"

    with pytest.raises(RuntimeError, match="empty assistant reply"):
        async for _ in stream_interview_turn("你好", user_id=user_id, db=db):
            pass


@pytest.mark.asyncio
async def test_stream_interview_turn_emits_report_event_on_closing(db, monkeypatch):
    """closing 阶段完成后，stream_interview_turn 在 done 前发出 report 事件，含 overall_score 字段。"""

    async def fake_graph_events(state):
        yield {"event": "token", "data": {"text": "感谢参与本次模拟面试。"}}
        yield {
            "event": "final",
            "data": {
                **state,
                "stage": "closing",
                "question_count": 5,
                "followup_count": 0,
                "assistant_message": "感谢参与本次模拟面试。",
                "report": {
                    "overall_score": 7.5,
                    "technical_depth": 4.0,
                    "quantified_results": 3.0,
                    "failure_tradeoffs": 4.0,
                    "structure": 3.5,
                    "highlights": ["表达清晰"],
                    "improvements": ["可补充量化数据"],
                },
            },
        }

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events", fake_graph_events
    )
    user_id = f"user_turn_report_{uuid4().hex}"

    events = [
        event
        async for event in stream_interview_turn("第五题回答", user_id=user_id, db=db)
    ]

    event_names = [e["event"] for e in events]
    assert event_names == ["delta", "state", "report", "done"]

    report_event = next(e for e in events if e["event"] == "report")
    assert report_event["data"]["overall_score"] == 7.5
    assert report_event["data"]["highlights"] == ["表达清晰"]


@pytest.mark.asyncio
async def test_stream_interview_turn_skips_report_event_when_empty(db, monkeypatch):
    """report_node 返回空 dict 时，不发 report 事件，closing 消息正常显示。"""

    async def fake_graph_events(state):
        yield {"event": "token", "data": {"text": "感谢参与。"}}
        yield {
            "event": "final",
            "data": {
                **state,
                "stage": "closing",
                "question_count": 5,
                "followup_count": 0,
                "assistant_message": "感谢参与。",
                "report": {},
            },
        }

    monkeypatch.setattr(
        "app.services.interview_turn.stream_interviewer_turn_events", fake_graph_events
    )
    user_id = f"user_turn_no_report_{uuid4().hex}"

    events = [
        event
        async for event in stream_interview_turn("第五题回答", user_id=user_id, db=db)
    ]

    event_names = [e["event"] for e in events]
    assert "report" not in event_names
    assert event_names == ["delta", "state", "done"]


# ---------------------------------------------------------------------------
# reset_interview_session 集成测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_interview_session_abandons_active_session(db):
    """reset 基本流程：in_progress session 被标记为 abandoned。"""
    user_id = f"user_reset_single_{uuid4().hex}"
    session, _ = await get_or_create_active_session(db, user_id=user_id)
    assert session.status == "in_progress"

    await reset_interview_session(db, user_id=user_id)

    await db.refresh(session)
    assert session.status == "abandoned"


@pytest.mark.asyncio
async def test_reset_interview_session_is_noop_when_no_active_session(db):
    """无 in_progress session 时，reset 是幂等的，不抛出异常。"""
    user_id = f"user_reset_noop_{uuid4().hex}"
    await reset_interview_session(db, user_id=user_id)


@pytest.mark.asyncio
async def test_reset_then_get_or_create_returns_fresh_session(db):
    """reset 后调用 get_or_create_active_session，应返回全新 session（id 不同，stage=opening）。

    回归：浏览器刷新触发 reset 完成后，再次进入应从 opening 阶段重新开始，而非复用旧进度。
    """
    user_id = f"user_reset_fresh_{uuid4().hex}"

    old_session, _ = await get_or_create_active_session(db, user_id=user_id)
    old_id = old_session.id

    await reset_interview_session(db, user_id=user_id)

    new_session, is_first_time = await get_or_create_active_session(db, user_id=user_id)

    assert new_session.id != old_id
    assert new_session.status == "in_progress"
    assert new_session.stage == "opening"
    assert is_first_time is False  # 用户已有历史，不是首次


@pytest.mark.asyncio
async def test_reset_does_not_affect_completed_sessions(db):
    """reset 只影响 in_progress session；completed session 不受影响。"""
    user_id = f"user_reset_completed_{uuid4().hex}"

    session, _ = await get_or_create_active_session(db, user_id=user_id)
    session.status = "completed"
    await db.commit()

    await reset_interview_session(db, user_id=user_id)

    await db.refresh(session)
    assert session.status == "completed"
