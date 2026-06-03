# backend/tests/unit/test_designer_consumes_job_intel.py
"""Designer 应消费 job_intel 的 job_interpretation 和 resume_match 字段。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_designer_prompt_contains_hard_requirements_and_gaps():
    """run_designer 组装出来的 prompt 应包含 job_intel 里的关键字段。"""
    from app.agents.designer.graph import run_designer

    inputs = {
        "focus": "new_question",
        "target_role": "后端工程师",
        "target_company": "字节",
        "user_background": "3 年 Python",
        "candidate_profile": {},
        "jd_context": None,
        "previous_questions": [],
        "prepared_questions": [],
        "current_question_index": 0,
        "evaluator_report": None,
        "messages": [],
        "job_intel": {
            "job_interpretation": {
                "hard_requirements": ["分布式系统", "高并发"],
                "soft_requirements": [],
                "hidden_bonuses": [],
                "summary": "",
            },
            "resume_match": {"strengths": ["Python"], "gaps": ["缺分布式"]},
        },
    }

    captured: dict[str, str] = {}

    class FakeResp:
        content = '{"question_text": "Q", "question_category": "technical", "focus_area": "x", "source": "llm"}'

    async def fake_ainvoke(messages):
        captured["system"] = messages[0].content
        return FakeResp()

    with patch("app.agents.designer.nodes._chat_model") as mock_model:
        mock_model.return_value.with_structured_output.return_value.ainvoke = fake_ainvoke
        await run_designer(inputs)

    assert "分布式系统" in captured["system"]
    assert "缺分布式" in captured["system"]
