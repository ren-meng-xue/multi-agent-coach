"""维度二质量护栏：用静态测试防止 prompt 回退。"""

from app.agents.designer.prompts import DESIGNER_DUAL_SYSTEM_PROMPT, DESIGNER_SYSTEM_PROMPT
from app.agents.interviewer.prompts import (
    CLOSING_SYSTEM_PROMPT,
    FOLLOWUP_SYSTEM_PROMPT,
    QUESTION_SYSTEM_PROMPT,
)
from app.agents.prepare.prompts import QUESTION_GEN_SYSTEM_PROMPT


def test_closing_prompt_does_not_leak_evaluation_result() -> None:
    """Q3-4：结束语只能感谢和告知后续报告，不应要求即时表现点评。"""
    forbidden = ("最终点评", "整体表现做", "表现得不错", "有待提高")

    for phrase in forbidden:
        assert phrase not in CLOSING_SYSTEM_PROMPT

    assert "感谢候选人" in CLOSING_SYSTEM_PROMPT
    assert "模拟面试已结束" in CLOSING_SYSTEM_PROMPT
    assert "结构化评估报告" in CLOSING_SYSTEM_PROMPT
    assert "严禁透露任何表现判断" in CLOSING_SYSTEM_PROMPT


def test_question_prompts_ban_leading_or_answer_revealing_questions() -> None:
    """Q3-2：面试问题不能暗示标准答案。"""
    prompts = [
        QUESTION_SYSTEM_PROMPT,
        FOLLOWUP_SYSTEM_PROMPT,
        DESIGNER_SYSTEM_PROMPT,
        DESIGNER_DUAL_SYSTEM_PROMPT,
    ]

    for prompt in prompts:
        assert "暗示标准答案" in prompt or "暗示正确答案" in prompt

    assert "你是否……对吗" in QUESTION_SYSTEM_PROMPT
    assert "你是否……对吗" in DESIGNER_SYSTEM_PROMPT


def test_question_prompts_avoid_reconfirming_known_resume_or_jd_facts() -> None:
    """Q1-3：基于已知事实追问，不重复确认简历/JD 已明示内容。"""
    prompts = [
        QUESTION_SYSTEM_PROMPT,
        FOLLOWUP_SYSTEM_PROMPT,
        DESIGNER_SYSTEM_PROMPT,
        DESIGNER_DUAL_SYSTEM_PROMPT,
        QUESTION_GEN_SYSTEM_PROMPT,
    ]

    for prompt in prompts:
        assert "重复确认" in prompt


def test_prepare_question_generation_requires_dimension_balance() -> None:
    """Q5-1/Q5-2：题库生成 prompt 必须要求能力维度覆盖和占比均衡。"""
    assert "所有一级岗位能力维度" in QUESTION_GEN_SYSTEM_PROMPT
    assert "至少覆盖 1 道题" in QUESTION_GEN_SYSTEM_PROMPT
    assert "单一 focus_area 占比超过 40%" in QUESTION_GEN_SYSTEM_PROMPT
    assert "technical/behavioral/system_design 各占比均衡" in QUESTION_GEN_SYSTEM_PROMPT
