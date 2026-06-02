"""Question Designer Agent 单元测试。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.designer import run_designer, run_designer_dual
from app.agents.designer.nodes import _DesignedQuestion, _DesignerDualOutput


@pytest.mark.asyncio
async def test_designer_agent_uses_prepared_question_first():
    out = await run_designer(
        {
            "focus": "new_question",
            "prepared_questions": [
                {
                    "question": "请讲讲你最近做过的一个 AI 应用项目。",
                    "category": "project",
                    "focus_area": "project_scope",
                }
            ],
            "current_question_index": 0,
        }
    )

    assert out["question_text"].startswith("请讲讲")
    assert out["question_category"] == "project"
    assert out["source"] == "prepared"


@pytest.mark.asyncio
async def test_designer_agent_rewrites_generic_question():
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(
        return_value=_DesignedQuestion(
            question_text="你能展开说说吗？",
            question_category="technical",
            focus_area="quantification",
        )
    )
    fake_model = MagicMock()
    fake_model.with_structured_output.return_value = fake_structured

    with patch("app.agents.designer.nodes._chat_model", return_value=fake_model):
        out = await run_designer(
            {
                "focus": "quantification",
                "previous_questions": [],
                "candidate_profile": {"latest_level": "junior"},
            }
        )

    assert out["question_text"].startswith("围绕quantification")
    assert "最终效果数据" in out["question_text"]


@pytest.mark.asyncio
async def test_designer_dual_returns_followup_and_new_question():
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(
        return_value=_DesignerDualOutput(
            followup_question="请量化缓存命中率提升了多少？",
            new_question="请讲一个你做过的系统设计取舍？",
        )
    )
    fake_model = MagicMock()
    fake_model.with_structured_output.return_value = fake_structured

    with patch("app.agents.designer.nodes._chat_model", return_value=fake_model):
        out = await run_designer_dual(
            {
                "focus": "dual",
                "target_role": "后端工程师",
                "previous_questions": [],
            }
        )

    assert out["followup_question"].startswith("请量化")
    assert out["new_question"].startswith("请讲")
    assert out["source"] == "llm"


@pytest.mark.asyncio
async def test_designer_dual_fallback_on_llm_error():
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
    fake_model = MagicMock()
    fake_model.with_structured_output.return_value = fake_structured

    with patch("app.agents.designer.nodes._chat_model", return_value=fake_model):
        out = await run_designer_dual(
            {
                "focus": "量化结果",
                "target_role": "后端工程师",
                "previous_questions": [],
            }
        )

    assert out["followup_question"]
    assert out["new_question"]


@pytest.mark.asyncio
async def test_designer_dual_uses_prepared_question_for_new_question():
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(
        return_value=_DesignerDualOutput(
            followup_question="请补充这个项目里的量化效果？",
            new_question="LLM 临时新题不应覆盖 prepared。",
        )
    )
    fake_model = MagicMock()
    fake_model.with_structured_output.return_value = fake_structured

    with patch("app.agents.designer.nodes._chat_model", return_value=fake_model):
        out = await run_designer_dual(
            {
                "focus": "dual",
                "target_role": "后端工程师",
                "previous_questions": [],
                "prepared_questions": [
                    {
                        "question": "请讲讲你准备题库里的第二个系统设计问题。",
                        "category": "technical",
                        "focus_area": "system_design",
                    }
                ],
                "current_question_index": 0,
            }
        )

    assert out["followup_question"].startswith("请补充")
    assert out["new_question"].startswith("请讲讲你准备题库")
    assert out["new_question_source"] == "prepared"
