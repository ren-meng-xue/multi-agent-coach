"""Evaluator Agent 单元测试。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.evaluator import run_evaluator


@pytest.mark.asyncio
async def test_evaluator_agent_returns_report_and_profile():
    fake_scoring = MagicMock(
        bullets=["覆盖缓存方案", "缺少量化指标"],
        technical_depth=7.0,
        quantified_results=3.0,
        failure_tradeoffs=5.0,
        structure=6.0,
        summary_score=5.5,
        candidate_level="junior",
        latent_signals=["caching_experience"],
        missing_dimensions=["quantification"],
    )

    with patch("app.agents.evaluator.nodes._evaluator_score", new=AsyncMock(return_value=fake_scoring)), \
        patch("app.agents.evaluator.nodes._chat_model", side_effect=RuntimeError("no llm")):
        out = await run_evaluator(
            {
                "session_id": "s1",
                "user_id": "u1",
                "target_role": "AI 工程师",
                "latest_answer": "我用了 Redis 缓存热门 query。",
                "conversation_context": "面试官：讲讲优化\n候选人：我用了 Redis 缓存热门 query。",
                "existing_profile": {},
                "question_index": 1,
                "followup_index": 0,
            }
        )

    assert out["scoring"]["summary_score"] == 5.5
    assert out["scoring"]["missing_dimensions"] == ["quantification"]
    assert out["updated_profile"]["latent_signals"] == ["caching_experience"]
    assert "建议围绕缺口" in out["report_text"]
