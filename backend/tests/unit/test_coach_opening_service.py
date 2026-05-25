"""Coach 开场词服务约束。"""

from app.services.coach_opening import COACH_OPENING_SYSTEM_PROMPT


def test_coach_opening_prompt_requires_direct_weakness_diagnosis():
    """老用户开场词必须约束 LLM 输出具体不足，而不是泛化总结。"""
    assert "最突出的不足或短板" in COACH_OPENING_SYSTEM_PROMPT
    assert "你在……方面不足" in COACH_OPENING_SYSTEM_PROMPT
    assert "weakness_summary" in COACH_OPENING_SYSTEM_PROMPT
    assert "evidence 必须是一段可直接展示给用户的证据文案" in COACH_OPENING_SYSTEM_PROMPT
    assert "禁止在 weakness_summary 和 evidence 中使用" in COACH_OPENING_SYSTEM_PROMPT
    assert "前端只会逐段渲染返回字段" in COACH_OPENING_SYSTEM_PROMPT
    assert "规律、改进机会、加强能力、提升空间、建议关注、频繁出现" in COACH_OPENING_SYSTEM_PROMPT
    assert "今天重点练" in COACH_OPENING_SYSTEM_PROMPT
