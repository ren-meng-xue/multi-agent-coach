"""LangGraph state for the multi-agent interviewer graph."""
from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

InterviewStage = Literal["opening", "interview", "closing"]


class TurnEvaluation(TypedDict, total=False):
    """单轮答题的评估结果，由 evaluator_node 写入。"""

    question_index: int
    followup_index: int
    bullets: list[str]
    technical_depth: float
    quantified_results: float
    failure_tradeoffs: float
    structure: float
    summary_score: float


class InterviewState(TypedDict, total=False):
    """Graph state shared by interviewer nodes."""

    # 基础
    session_id: str
    user_id: str
    is_first_time: bool
    target_role: str
    target_company: str
    user_background: str
    messages: list[BaseMessage]
    stage: InterviewStage
    question_count: int
    total_questions: int
    followup_count: int
    max_followups: int
    assistant_message: str

    # 准备阶段产出（沿用 Phase 3）
    jd_context: dict[str, Any] | None
    prepared_questions: list[dict[str, Any]]
    current_question_index: int

    # MASTER 动态调度
    chain: list[str]  # 本轮 chain，由 master_node 输出
    master_reason: str  # log 用，不展示
    turn_evaluations: list[TurnEvaluation]  # 累积所有轮次评估，report_node 聚合

    # 报告
    report: dict[str, Any]

