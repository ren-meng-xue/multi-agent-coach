"""LangGraph state for the multi-agent interviewer graph."""
from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

InterviewStage = Literal["opening", "interview", "closing"]


CandidateLevel = Literal["beginner", "junior", "mid", "senior"]


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
    # Phase 4+：候选人建模 + 隐含信号
    candidate_level: CandidateLevel
    latent_signals: list[str]
    missing_dimensions: list[str]
    followup_would_help: bool
    is_repeated_answer: bool


class CandidateProfile(TypedDict, total=False):
    """跨轮累积的候选人画像（仅 session 内）。"""

    latest_level: CandidateLevel
    latent_signals: list[str]  # 累积去重保序
    last_updated_turn: int


class InterviewState(TypedDict, total=False):
    """Graph state shared-1 by interviewer nodes."""

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
    job_intel: dict | None         # 来自 PrepareState，跨阶段透传；MCP 不可用时为 None
    prepared_questions: list[dict[str, Any]]
    current_question_index: int

    # MASTER 动态调度
    chain: list[str]  # 本轮 chain，由 master_node 输出
    master_reason: str  # log 用，不展示
    turn_evaluations: list[TurnEvaluation]  # 累积所有轮次评估，report_node 聚合

    # Phase 4+：候选人建模 + 追问方向
    candidate_profile: CandidateProfile  # 跨轮累积
    followup_focus: str  # 由 master 输出，followup 消费，单轮有效

    # Chief Interviewer ReAct loop
    chief_iteration: int
    chief_messages: list[BaseMessage]
    chief_thoughts: list[str]
    chief_tool_results: list[dict[str, Any]]
    evaluator_report: dict[str, Any] | None
    designer_output: dict[str, Any] | None
    designer_dual_output: dict[str, Any] | None

    # 报告
    qa_bank_items: list[dict[str, Any]] | None
    use_qa_bank: bool
    resume_text: str | None
    report: dict[str, Any]
