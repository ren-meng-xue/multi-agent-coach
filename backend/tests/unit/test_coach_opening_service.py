"""Coach 开场词服务约束。"""

from app.services.coach_opening import COACH_OPENING_SYSTEM_PROMPT


def test_coach_opening_prompt_requires_direct_weakness_diagnosis():
    """新 prompt 必须包含核心约束：用数据说话、禁止泛化、明确下一步。"""
    # 必须有关键输出字段
    assert "weakness_summary" in COACH_OPENING_SYSTEM_PROMPT
    assert "evidence" in COACH_OPENING_SYSTEM_PROMPT
    assert "focus_today" in COACH_OPENING_SYSTEM_PROMPT

    # 必须指导 LLM 用维度分说话
    assert "recent_sessions" in COACH_OPENING_SYSTEM_PROMPT
    assert "分数最低" in COACH_OPENING_SYSTEM_PROMPT

    # 必须禁止泛化表达
    assert "提升空间" in COACH_OPENING_SYSTEM_PROMPT
    assert "规律" in COACH_OPENING_SYSTEM_PROMPT
    assert "禁止" in COACH_OPENING_SYSTEM_PROMPT

    # 必须约束 focus_today 格式
    assert "今天重点练" in COACH_OPENING_SYSTEM_PROMPT

    # 必须包含岗位信息使用说明
    assert "practiced_roles" in COACH_OPENING_SYSTEM_PROMPT

    # 前端渲染约束
    assert "逐段渲染" in COACH_OPENING_SYSTEM_PROMPT


def test_coach_opening_response_has_memory_hint_slots():
    """schema 必须提供 long_memory_hints / hobby_hints 默认空槽，为第五步记忆 agent 预留位。"""
    from app.schemas.interview import CoachOpeningMessageResponse

    response = CoachOpeningMessageResponse(
        greeting="hi",
        weakness_summary=None,
        evidence=None,
        focus_today="练 X",
        cta_type="new",
    )
    assert response.long_memory_hints == []
    assert response.hobby_hints == []


def test_fallback_opening_includes_memory_hint_slots_for_new_user():
    from app.services.coach_opening import CoachHistoryContext, _fallback_opening_message

    ctx = CoachHistoryContext(
        session_count=0,
        recent_scores=[],
        pass_rate=0.0,
        common_issues={},
        trend="flat",
        is_new=True,
        practiced_roles={},
        recent_sessions=[],
    )
    response = _fallback_opening_message(ctx)
    assert response.long_memory_hints == []
    assert response.hobby_hints == []


def test_fallback_opening_includes_memory_hint_slots_for_returning_user():
    from app.services.coach_opening import CoachHistoryContext, _fallback_opening_message

    ctx = CoachHistoryContext(
        session_count=3,
        recent_scores=[3.2, 3.0, 2.8],
        pass_rate=0.33,
        common_issues={"量化欠缺": 2},
        trend="declining",
        is_new=False,
        practiced_roles={"AI Agent 工程师": 3},
        recent_sessions=[],
    )
    response = _fallback_opening_message(ctx)
    assert response.long_memory_hints == []
    assert response.hobby_hints == []


