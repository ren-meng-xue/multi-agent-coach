"""Unit tests for stream_prepare_and_launch generator."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.prepare.state import PrepareState
from app.api.v1.prepare import _apply_prepare_trace_event, stream_prepare_and_launch


def _make_state(need_direction: bool = False) -> PrepareState:
    return {
        "session_id": "test-session",
        "user_id": "user-1",
        "user_direction": None if need_direction else "前端工程师",
        "user_background": None,
        "jd_raw": None,
        "weak_areas": [],
    }


MOCK_PREPARE_EVENTS_NORMAL = [
    {"event": "node_start", "data": {"node": "supervisor", "label": "调度"}},
    {
        "event": "node_done",
        "data": {"node": "supervisor", "elapsed_ms": 100, "next_action": "question_gen", "need_direction": False},
    },
    {"event": "node_start", "data": {"node": "question_gen", "label": "出题"}},
    {"event": "node_done", "data": {"node": "question_gen", "elapsed_ms": 200}},
    {
        "event": "done",
        "data": {
            "jd_context": None,
            "prepared_questions": [
                {"id": 1, "question": "Q1", "category": "technical", "focus_area": "f", "priority": 1}
            ],
            "summary": "1道题",
            "direction": "前端工程师",
        },
    },
]

MOCK_PREPARE_EVENTS_NEED_DIRECTION = [
    {"event": "node_start", "data": {"node": "supervisor", "label": "调度"}},
    {
        "event": "node_done",
        "data": {"node": "supervisor", "elapsed_ms": 100, "next_action": "need_direction", "need_direction": True},
    },
]

MOCK_TURN_EVENTS = [
    {"event": "node_start", "data": {"node": "master", "label": "调度", "phase": "start"}},
    {"event": "node_done", "data": {"node": "master", "elapsed_ms": 50, "phase": "done"}},
    {"event": "delta", "data": {"text": "好的，第一题："}},
    {"event": "state", "data": {"stage": "interview", "question_count": 1, "total_questions": 5}},
    {"event": "done", "data": {}},
]


async def _collect(gen) -> list[dict]:
    result = []
    async for ev in gen:
        result.append(ev)
    return result


@pytest.mark.asyncio
async def test_happy_path_event_sequence():
    """正常流：prepare done → launch 节点 → phase_change → 前缀 turn_* 事件 → turn_done。"""
    mock_db = AsyncMock()

    async def mock_prepare_stream(state):
        for ev in MOCK_PREPARE_EVENTS_NORMAL:
            yield ev

    # 注意：stream_interview_turn 的 message 是 positional 参数；mock 必须能接受 positional，
    # 否则 side_effect 透传时会触发 TypeError。
    async def mock_turn_stream(message, **kwargs):
        assert message == "__START__"
        for ev in MOCK_TURN_EVENTS:
            yield ev

    with (
        patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_prepare_stream),
        patch("app.api.v1.prepare.stream_interview_turn", side_effect=mock_turn_stream),
        patch("app.api.v1.prepare._persist_prepare_trace", new_callable=AsyncMock),
    ):
        events = await _collect(stream_prepare_and_launch(_make_state(), db=mock_db))

    event_names = [e["event"] for e in events]

    # prepare 事件原样透传
    assert "node_start" in event_names
    # service-side done 应被 generator 吞掉，整条流里只有 prepare 阶段那一次 done
    assert event_names.count("done") == 1

    launch_start_idx = next(
        i for i, e in enumerate(events) if e["event"] == "node_start" and e["data"]["node"] == "launch"
    )
    launch_done_idx = next(
        i for i, e in enumerate(events) if e["event"] == "node_done" and e["data"]["node"] == "launch"
    )
    phase_change_idx = next(i for i, e in enumerate(events) if e["event"] == "phase_change")
    done_idx = next(i for i, e in enumerate(events) if e["event"] == "done")

    # 顺序：prepare.done < launch_start < launch_done < phase_change < turn 事件
    assert done_idx < launch_start_idx < launch_done_idx < phase_change_idx

    # phase_change 携带 turn_id
    assert "turn_id" in events[phase_change_idx]["data"]

    # turn 事件被加 turn_ 前缀
    turn_events = [e for e in events if e["event"].startswith("turn_")]
    assert any(e["event"] == "turn_delta" for e in turn_events)
    assert any(e["event"] == "turn_state" for e in turn_events)
    assert events[-1]["event"] == "turn_done"


@pytest.mark.asyncio
async def test_need_direction_stops_before_launch():
    """need_direction=True：prepare 阶段结束后直接返回，不发 launch / phase_change / turn 事件。"""
    mock_db = AsyncMock()

    async def mock_prepare_stream(state):
        for ev in MOCK_PREPARE_EVENTS_NEED_DIRECTION:
            yield ev

    with (
        patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_prepare_stream),
        patch("app.api.v1.prepare.stream_interview_turn") as mock_turn,
    ):
        events = await _collect(
            stream_prepare_and_launch(_make_state(need_direction=True), db=mock_db)
        )

    mock_turn.assert_not_called()
    assert all(e["event"] != "phase_change" for e in events)
    assert all(e["event"] != "turn_done" for e in events)
    assert all(
        not (e["event"] == "node_start" and e["data"].get("node") == "launch") for e in events
    )


@pytest.mark.asyncio
async def test_prepared_questions_passed_to_turn():
    """prepared_questions 从 done 事件提取后正确透传给 stream_interview_turn。"""
    mock_db = AsyncMock()
    captured: dict = {}

    async def mock_prepare_stream(state):
        for ev in MOCK_PREPARE_EVENTS_NORMAL:
            yield ev

    async def mock_turn_stream(message, **kwargs):
        captured["message"] = message
        captured.update(kwargs)
        for ev in MOCK_TURN_EVENTS:
            yield ev

    with (
        patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_prepare_stream),
        patch("app.api.v1.prepare.stream_interview_turn", side_effect=mock_turn_stream),
        patch("app.api.v1.prepare._persist_prepare_trace", new_callable=AsyncMock),
    ):
        await _collect(stream_prepare_and_launch(_make_state(), db=mock_db))

    assert captured.get("message") == "__START__"
    pqs = captured.get("prepared_questions", [])
    assert len(pqs) == 1
    assert pqs[0]["question"] == "Q1"


def test_prepare_trace_persists_structured_node_done_fields():
    """node_done 新增结构化字段应进入 prepare_trace，刷新恢复时不退化为空状态。"""
    payload = {"nodes": [{"id": "research_agent", "label": "调研", "status": "running", "tokens": ""}]}

    _apply_prepare_trace_event(
        payload,
        {
            "event": "node_done",
            "data": {
                "node": "research_agent",
                "elapsed_ms": 123,
                "record_count": 7,
                "react_iterations": 2,
                "react_tool_count": 4,
                "company_name": "Acme",
                "gaps": ["缺少大规模系统经验"],
            },
        },
    )

    node = payload["nodes"][0]
    assert node["status"] == "done"
    assert node["elapsedMs"] == 123
    assert node["reactStatus"] == "done"
    assert node["recordCount"] == 7
    assert node["reactIterations"] == 2
    assert node["reactToolCount"] == 4
    assert node["companyName"] == "Acme"
    assert node["gaps"] == ["缺少大规模系统经验"]

    payload = {"nodes": [{"id": "jd_analysis", "label": "JD", "status": "running", "tokens": ""}]}
    _apply_prepare_trace_event(
        payload,
        {
            "event": "node_done",
            "data": {
                "node": "jd_analysis",
                "jd_company": "Acme",
                "jd_role": "Senior Backend",
                "jd_difficulty": "高",
                "jd_key_skills": ["Python", "Redis"],
            },
        },
    )
    node = payload["nodes"][0]
    assert node["jdCompany"] == "Acme"
    assert node["jdRole"] == "Senior Backend"
    assert node["jdDifficulty"] == "高"
    assert node["jdKeySkills"] == ["Python", "Redis"]

    payload = {"nodes": [{"id": "question_gen", "label": "出题", "status": "running", "tokens": ""}]}
    _apply_prepare_trace_event(
        payload,
        {
            "event": "node_done",
            "data": {
                "node": "question_gen",
                "question_stats": {"technical": 3, "behavioral": 1},
                "question_total": 4,
            },
        },
    )
    node = payload["nodes"][0]
    assert node["questionStats"] == {"technical": 3, "behavioral": 1}
    assert node["questionTotal"] == 4
