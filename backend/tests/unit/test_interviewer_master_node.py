"""master_node 单元测试：chain 决策 + 合法性约束 + 流式 bullet。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from app.agents.interviewer.nodes import master_node


@pytest.mark.asyncio
async def test_master_first_turn_forces_ask_question():
    """question_count == 0：强制 chain = ['ask_question']，即使 LLM 输出别的。"""
    fake_decision = MagicMock(chain=["evaluator", "followup"], reason="LLM 的随意输出")
    state = {"question_count": 0, "messages": []}
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["ask_question"]


@pytest.mark.asyncio
async def test_master_exhausted_forces_closing():
    """题数耗尽且追问耗尽：强制 chain = ['closing']。"""
    fake_decision = MagicMock(chain=["evaluator", "followup"], reason="")
    state = {
        "question_count": 5,
        "total_questions": 5,
        "followup_count": 2,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["closing"]


@pytest.mark.asyncio
async def test_master_max_followups_forces_next_question_before_final_question():
    """当前题追问达到上限但整场未结束时，必须推进到下一题。"""
    fake_decision = MagicMock(chain=["evaluator", "followup"], reason="")
    state = {
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 2,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["evaluator", "ask_question"]


@pytest.mark.asyncio
async def test_master_normal_chain_passes_through():
    """中段轮次：LLM 的 chain 不被覆盖。"""
    fake_decision = MagicMock(chain=["evaluator", "followup"], reason="OK")
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["evaluator", "followup"]


@pytest.mark.asyncio
async def test_master_strips_after_closing():
    """chain 含 closing 时，closing 之后的节点被丢弃。"""
    fake_decision = MagicMock(chain=["closing", "ask_question"], reason="")
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["closing"]


@pytest.mark.asyncio
async def test_master_appends_followup_when_tail_is_evaluator():
    """末尾是 evaluator（非合法终态）时，追加 followup。"""
    fake_decision = MagicMock(chain=["evaluator"], reason="")
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"][-1] in {"followup", "ask_question", "closing"}
    assert result["chain"] == ["evaluator", "followup"]


@pytest.mark.asyncio
async def test_master_phase2_failure_falls_back():
    """Phase 2 抛错：fallback chain。"""
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(side_effect=RuntimeError("LLM down"))):
        result = await master_node(state)
    assert result["chain"] == ["evaluator", "followup"]


@pytest.mark.asyncio
async def test_master_empty_chain_falls_back():
    fake_decision = MagicMock(chain=[], reason="")
    state = {
        "question_count": 2,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["chain"] == ["evaluator", "followup"]


# ─────────────────────────────────────────────
# Phase 4+ schema 扩展（Step 1）
# ─────────────────────────────────────────────

def test_master_decision_defaults_followup_focus():
    """_InterviewMasterDecision 必须默认 followup_focus='' 以兼容旧 LLM 输出。"""
    from app.agents.interviewer.nodes import _InterviewMasterDecision

    d = _InterviewMasterDecision()
    assert d.followup_focus == ""


# ─────────────────────────────────────────────
# Phase 4+ Step 3 业务逻辑测试
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_master_writes_followup_focus_to_state():
    from app.agents.interviewer.nodes import master_node
    fake_decision = MagicMock(
        chain=["evaluator", "followup"],
        reason="深挖架构",
        followup_focus="architecture",
    )
    state = {
        "question_count": 1,  # 非首轮
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [HumanMessage(content="我用了 Redis 做缓存")],
        "candidate_profile": {"latest_level": "junior", "latent_signals": ["caching"]},
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock()), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(return_value=fake_decision)):
        result = await master_node(state)
    assert result["followup_focus"] == "architecture"
    assert result["chain"] == ["evaluator", "followup"]


@pytest.mark.asyncio
async def test_master_context_contains_candidate_profile():
    from app.agents.interviewer.nodes import master_node
    captured = {}
    fake_decision = MagicMock(chain=["evaluator", "followup"], reason="", followup_focus="")
    async def fake_decide(context: str):
        captured["context"] = context
        return fake_decision
    state = {
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [HumanMessage(content="我处理事件流")],
        "candidate_profile": {
            "latest_level": "beginner",
            "latent_signals": ["workflow_orchestration"],
        },
    }
    with patch("app.agents.interviewer.nodes._master_phase1_stream", new=AsyncMock()), \
         patch("app.agents.interviewer.nodes._master_phase2_decide", new=AsyncMock(side_effect=fake_decide)):
        await master_node(state)
    assert "beginner" in captured["context"]
    assert "workflow_orchestration" in captured["context"]
