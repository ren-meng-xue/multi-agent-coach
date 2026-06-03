# backend/tests/unit/test_coach_consumes_job_intel.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.agents.coach.state import CoachState

# 模拟 async iterator
async def aiter(items):
    for item in items:
        yield item

@pytest.mark.asyncio
async def test_coach_review_prompt_includes_gaps_and_prep_suggestions():
    """Coach 复盘 prompt 应引用 job_intel.resume_match.gaps 和 prep_suggestions。"""
    from app.agents.coach.nodes import _generate_review_text

    state: CoachState = {
        "candidate_memory": {},
        "last_session_report": {},
        "target_role": "后端工程师",
        "resume_summary": "3 年 Python",
        "job_intel": {
            "resume_match": {"strengths": ["Python"], "gaps": ["缺分布式", "未做过大流量"]},
            "prep_suggestions": [
                {"title": "3 天补分布式", "content": "看 DDIA 1-4 章"},
            ],
        },
    }

    captured = {}
    mock_chunk = MagicMock()
    mock_chunk.content = "复盘完成"

    async def mock_astream(messages):
        captured["human"] = messages[1].content
        yield mock_chunk

    with patch("app.agents.coach.nodes._chat_model") as mock_model:
        mock_model.return_value.with_config.return_value.astream = mock_astream
        await _generate_review_text(state)

    assert "缺分布式" in captured["human"]
    assert "3 天补分布式" in captured["human"]
