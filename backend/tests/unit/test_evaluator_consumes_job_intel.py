# backend/tests/unit/test_evaluator_consumes_job_intel.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_evaluator_prompt_contains_hard_requirements_as_dimension():
    """evaluator 的 prompt 应把 job_intel.hard_requirements 当评分维度引用。"""
    from app.agents.evaluator.graph import run_evaluator

    inputs = {
        "session_id": "s1",
        "user_id": "u1",
        "target_role": "后端工程师",
        "latest_answer": "我用 Redis 做了缓存",
        "conversation_context": "",
        "existing_profile": {},
        "question_index": 0,
        "followup_index": 0,
        "db": None,
        "job_intel": {
            "job_interpretation": {
                "hard_requirements": ["分布式系统", "高并发"],
            },
        },
    }

    captured = {}

    class FakeResp:
        content = '{"scoring": {"summary_score": 7}, "report_text": "ok", "updated_profile": {}}'

    async def fake_ainvoke(messages):
        captured["system"] = messages[0].content
        return FakeResp()

    with patch("app.agents.evaluator.nodes._chat_model") as mock_model:
        mock_model.return_value.with_structured_output.return_value.ainvoke = fake_ainvoke
        mock_model.return_value.ainvoke = fake_ainvoke
        await run_evaluator(inputs)

    assert "分布式系统" in captured["system"]
