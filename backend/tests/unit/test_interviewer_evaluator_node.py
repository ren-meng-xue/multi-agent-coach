"""evaluator_node 单元测试：写入 turn_evaluations + 失败降级。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.interviewer.nodes import evaluator_node


@pytest.mark.asyncio
async def test_evaluator_writes_turn_evaluation_into_state():
    fake_scoring = MagicMock(
        bullets=["覆盖 CAP", "缺量化指标"],
        technical_depth=7.0,
        quantified_results=4.0,
        failure_tradeoffs=6.0,
        structure=7.5,
        summary_score=6.1,
    )
    state = {
        "question_count": 2,
        "followup_count": 0,
        "current_question_index": 2,
        "turn_evaluations": [],
        "messages": [HumanMessage(content="我会用 CAP 解决"), AIMessage(content="...")],
    }
    with patch("app.agents.interviewer.nodes._evaluator_reason_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._evaluator_score", new=AsyncMock(return_value=fake_scoring)):
        result = await evaluator_node(state)
    evals = result["turn_evaluations"]
    assert len(evals) == 1
    assert evals[0]["technical_depth"] == 7.0
    assert evals[0]["summary_score"] == 6.1
    assert evals[0]["bullets"] == ["覆盖 CAP", "缺量化指标"]
    assert evals[0]["question_index"] == 2


@pytest.mark.asyncio
async def test_evaluator_failure_passthrough_without_writing():
    """LLM 失败时不写 turn_evaluations，但不抛错（保证主链路继续）。"""
    state = {
        "question_count": 2,
        "followup_count": 0,
        "current_question_index": 2,
        "turn_evaluations": [],
        "messages": [],
    }
    with patch("app.agents.interviewer.nodes._evaluator_reason_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._evaluator_score", new=AsyncMock(side_effect=RuntimeError("down"))):
        result = await evaluator_node(state)
    assert result["turn_evaluations"] == []


@pytest.mark.asyncio
async def test_evaluator_appends_not_overwrites():
    existing = [{"question_index": 1, "summary_score": 7.0, "bullets": []}]
    fake_scoring = MagicMock(
        bullets=["b1"],
        technical_depth=8.0,
        quantified_results=8.0,
        failure_tradeoffs=8.0,
        structure=8.0,
        summary_score=8.0,
    )
    state = {
        "question_count": 2,
        "followup_count": 1,
        "current_question_index": 2,
        "turn_evaluations": existing,
        "messages": [],
    }
    with patch("app.agents.interviewer.nodes._evaluator_reason_stream", new=AsyncMock(return_value=None)), \
         patch("app.agents.interviewer.nodes._evaluator_score", new=AsyncMock(return_value=fake_scoring)):
        result = await evaluator_node(state)
    assert len(result["turn_evaluations"]) == 2
    assert result["turn_evaluations"][0]["summary_score"] == 7.0


# ─────────────────────────────────────────────
# Phase 4+ schema 扩展（Step 1）
# ─────────────────────────────────────────────

def test_turn_evaluation_accepts_new_optional_fields():
    """TurnEvaluation TypedDict 接受 candidate_level / latent_signals / missing_dimensions。"""
    from app.agents.interviewer.state import TurnEvaluation

    entry: TurnEvaluation = {
        "question_index": 1,
        "candidate_level": "junior",
        "latent_signals": ["workflow_orchestration"],
        "missing_dimensions": ["quantification"],
    }
    assert entry["candidate_level"] == "junior"
    assert entry["latent_signals"] == ["workflow_orchestration"]
    assert entry["missing_dimensions"] == ["quantification"]


def test_evaluator_scoring_defaults_new_fields():
    """_EvaluatorScoring 新字段必须有默认值，避免 LLM 缺字段时崩溃。"""
    from app.agents.interviewer.nodes import _EvaluatorScoring

    s = _EvaluatorScoring()
    assert s.candidate_level == "junior"
    assert s.latent_signals == []
    assert s.missing_dimensions == []


def test_candidate_profile_typed_dict_shape():
    """CandidateProfile TypedDict 字段可读写。"""
    from app.agents.interviewer.state import CandidateProfile

    profile: CandidateProfile = {
        "latest_level": "mid",
        "latent_signals": ["a", "b"],
        "last_updated_turn": 3,
    }
    assert profile["latest_level"] == "mid"
    assert profile["latent_signals"] == ["a", "b"]
    assert profile["last_updated_turn"] == 3
