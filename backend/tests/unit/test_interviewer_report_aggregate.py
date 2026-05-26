"""report_node 聚合 turn_evaluations 测试。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.interviewer.nodes import report_node


@pytest.mark.asyncio
async def test_report_averages_turn_evaluations():
    """两轮评估：四维取均值，overall = 各维均值。"""
    state = {
        "messages": [],
        "turn_evaluations": [
            {
                "question_index": 1, "followup_index": 0, "bullets": ["a"],
                "technical_depth": 6.0, "quantified_results": 4.0,
                "failure_tradeoffs": 7.0, "structure": 5.0, "summary_score": 5.5,
            },
            {
                "question_index": 2, "followup_index": 0, "bullets": ["b"],
                "technical_depth": 8.0, "quantified_results": 8.0,
                "failure_tradeoffs": 7.0, "structure": 9.0, "summary_score": 8.0,
            },
        ],
    }
    fake_text = MagicMock(
        highlights=["亮点1"], improvements=["改进1"],
        key_concepts=["CAP"], common_mistakes=["缺指标"],
    )
    with patch("app.agents.interviewer.nodes._report_aggregate_text", new=AsyncMock(return_value=fake_text)):
        result = await report_node(state)
    report = result["report"]
    assert report["technical_depth"] == pytest.approx(7.0)
    assert report["quantified_results"] == pytest.approx(6.0)
    assert report["structure"] == pytest.approx(7.0)
    expected_overall = (7.0 + 6.0 + 7.0 + 7.0) / 4
    assert report["overall_score"] == pytest.approx(expected_overall, rel=0.01)
    assert report["highlights"] == ["亮点1"]


@pytest.mark.asyncio
async def test_report_empty_evaluations_uses_fallback():
    """无 turn_evaluations 时走 LLM 整场评估降级路径。"""
    fake_fallback = MagicMock(
        overall_score=6.5,
        technical_depth=6.0, quantified_results=5.0,
        failure_tradeoffs=7.0, structure=8.0,
        highlights=["h"], improvements=["i"],
        key_concepts=["k"], common_mistakes=["m"],
    )
    state = {"messages": [], "turn_evaluations": []}
    with patch("app.agents.interviewer.nodes._report_fallback_full_eval", new=AsyncMock(return_value=fake_fallback)):
        result = await report_node(state)
    report = result["report"]
    assert report["overall_score"] == 6.5
    assert report["technical_depth"] == 6.0


@pytest.mark.asyncio
async def test_report_text_failure_returns_empty_report():
    state = {
        "messages": [],
        "turn_evaluations": [{
            "question_index": 1, "followup_index": 0, "bullets": [],
            "technical_depth": 5.0, "quantified_results": 5.0,
            "failure_tradeoffs": 5.0, "structure": 5.0, "summary_score": 5.0,
        }],
    }
    with patch("app.agents.interviewer.nodes._report_aggregate_text", new=AsyncMock(side_effect=RuntimeError("LLM"))):
        result = await report_node(state)
    assert result["report"] == {}
