from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.eval.dimensions import JudgeMode


class EvalRunResponse(BaseModel):
    id: UUID
    name: str | None = None
    suite_name: str | None = None
    judge_mode: str
    judge_model: str
    system_version: str | None = None
    status: str
    total_cases: int
    completed_cases: int
    aggregate_scores: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EvalRunSummary(EvalRunResponse):
    results_by_type: dict  # {target_type: {avg, pass_rate, count}}


class EvalResultResponse(BaseModel):
    id: UUID
    case_key: str
    target_type: str
    judge_scores: dict
    judge_reasoning: str | None
    binary_pass: bool | None
    overall_score: float | None
    latency_ms: int | None
    retry_count: int
    model_config = ConfigDict(from_attributes=True)


class TriggerEvalRequest(BaseModel):
    suite: str
    judge_model: str | None = None
    judge_mode: JudgeMode = JudgeMode.RUBRIC
    limit: int | None = None  # 限制 case 数量（快速冒烟）
    target_types: list[str] | None = None
    system_version: str | None = None


class CompareRequest(BaseModel):
    run_a_id: UUID
    run_b_id: UUID
    metric: str = "overall"


class TrendResponse(BaseModel):
    suite_name: str
    metric: str
    points: list[dict]
    degraded: bool
    trend: str  # improving/stable/declining


class EvalSuiteResponse(BaseModel):
    id: UUID
    name: str
    version: int
    description: str | None
    judge_mode: str
    case_count: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
