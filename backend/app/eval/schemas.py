from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.eval.dimensions import JudgeMode, TargetType

PASS_THRESHOLD = 7.0


class RubricDimensionScore(BaseModel):
    dimension_name: str
    score: float = Field(ge=0, le=10)
    reasoning: str


class RubricJudgeScore(BaseModel):
    target_type: str
    dimensions: list[RubricDimensionScore]
    overall: float
    reasoning: str

    @property
    def passed(self) -> bool:
        return self.overall >= PASS_THRESHOLD


class ComparativeScore(BaseModel):
    a_better: bool
    b_better: bool
    tie: bool
    reasoning: str
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_exclusive_booleans(self) -> "ComparativeScore":
        true_count = sum([self.a_better, self.b_better, self.tie])
        if true_count != 1:
            raise ValueError("Exactly one of a_better, b_better, or tie must be True")
        return self


class BinaryScore(BaseModel):
    passed: bool
    reasoning: str
    confidence: float = Field(ge=0, le=1)


class ReflectionScore(BaseModel):
    original_confidence: float
    adjusted: bool
    new_overall: float | None
    reasoning: str


class BenchmarkCase(BaseModel):
    id: str
    target_type: TargetType
    label: str
    description: str
    difficulty: Literal["easy", "medium", "hard"]
    tags: list[str]
    input_json: dict
    system_output: dict | None = None
    golden: dict | None = None


class BenchmarkSuite(BaseModel):
    name: str
    version: str
    description: str
    judge_mode: JudgeMode
    cases: list[BenchmarkCase]


class JudgeConfig(BaseModel):
    model: str = "gpt-4o"
    mode: JudgeMode = JudgeMode.RUBRIC
    temperature: float = 0.0
