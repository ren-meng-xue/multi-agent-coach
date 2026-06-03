# backend/tests/unit/test_chief_consumes_company_profile.py
import pytest


def test_chief_context_includes_company_profile():
    """_chief_context 应在 state 有 job_intel.company_profile 时把它拼进上下文。"""
    from app.agents.interviewer.chief import _chief_context

    state = {
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "target_role": "后端工程师",
        "messages": [],
        "job_intel": {
            "company_profile": {
                "summary": "字节国际化团队，节奏快，技术栈以 Go 为主",
                "tags": ["扁平管理", "快节奏"],
            },
        },
    }

    ctx = _chief_context(state)
    assert "字节国际化团队" in ctx
    assert "扁平管理" in ctx
