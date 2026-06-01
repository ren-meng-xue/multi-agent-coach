"""回归测试：用户短消息表达终止意图必须强制进入 closing。"""
from langchain_core.messages import HumanMessage

from app.agents.interviewer.nodes import _enforce_chain
from app.agents.interviewer.state import InterviewState


def _state(last_user_text: str, *, question_count: int = 2) -> InterviewState:
    return {
        "messages": [HumanMessage(content=last_user_text)],
        "question_count": question_count,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
    }


def test_lone_jieshu_forces_closing() -> None:
    """孤立的'结束'两字必须命中兜底，强制 closing。"""
    assert _enforce_chain(["followup"], _state("结束")) == ["closing"]


def test_jieshu_ba_forces_closing() -> None:
    """老关键词'结束吧'继续命中（回归保护）。"""
    assert _enforce_chain(["followup"], _state("结束吧")) == ["closing"]


def test_short_negative_intents_force_closing() -> None:
    """常见短词意图都应命中。"""
    for msg in ["够了", "算了", "停止", "我说完了", "不想继续了"]:
        assert _enforce_chain(["followup"], _state(msg)) == ["closing"], msg


def test_long_message_with_jieshu_not_force_closing() -> None:
    """'结束'出现在 >=15 字长句中（话题语义），不应被兜底误判为终止。"""
    long_msg = "项目结束后我重构了高并发模块，吞吐提升了三倍以上呢"
    result = _enforce_chain(["evaluator", "followup"], _state(long_msg))
    assert "closing" not in result
