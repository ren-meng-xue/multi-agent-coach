import pytest
from pydantic import ValidationError

from app.eval.dimensions import JudgeMode, TargetType
from app.eval.schemas import (
    BenchmarkCase,
    BenchmarkSuite,
    BinaryScore,
    ComparativeScore,
    JudgeConfig,
    RubricDimensionScore,
)


def test_benchmark_case_validation():
    # Missing id
    with pytest.raises(ValidationError):
        BenchmarkCase(
            target_type=TargetType.QUESTION,
            label="test",
            description="desc",
            difficulty="easy",
            tags=[],
            input_json={},
        )

    # Missing target_type
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="1",
            label="test",
            description="desc",
            difficulty="easy",
            tags=[],
            input_json={},
        )

    # Valid case
    case = BenchmarkCase(
        id="1",
        target_type=TargetType.QUESTION,
        label="test",
        description="desc",
        difficulty="easy",
        tags=[],
        input_json={},
    )
    assert case.id == "1"


def test_benchmark_suite_validation():
    case = BenchmarkCase(
        id="1",
        target_type=TargetType.QUESTION,
        label="test",
        description="desc",
        difficulty="easy",
        tags=[],
        input_json={},
    )
    
    # Missing name
    with pytest.raises(ValidationError):
        BenchmarkSuite(
            version="1.0",
            description="desc",
            judge_mode=JudgeMode.RUBRIC,
            cases=[case],
        )

    # Valid suite
    suite = BenchmarkSuite(
        name="test suite",
        version="1.0",
        description="desc",
        judge_mode=JudgeMode.RUBRIC,
        cases=[case],
    )
    assert suite.name == "test suite"


def test_rubric_dimension_score_range():
    # Score too low
    with pytest.raises(ValidationError):
        RubricDimensionScore(dimension_name="test", score=-1.0, reasoning="bad")

    # Score too high
    with pytest.raises(ValidationError):
        RubricDimensionScore(dimension_name="test", score=11.0, reasoning="bad")

    # Valid score
    score = RubricDimensionScore(dimension_name="test", score=8.5, reasoning="good")
    assert score.score == 8.5


def test_comparative_score_validation():
    # ComparativeScore has no custom validator in my skeleton yet, 
    # but the prompt says: "验证 ComparativeScore 三个 bool 不能同时为 True"
    # I should add a model_validator to ComparativeScore in schemas.py later.
    # For now, let's see if it fails as expected if I add the test.
    
    # Actually, the prompt says "验证", so I should probably implement the validation in schemas.py too.
    # But for TDD, I'll write the test that expects validation.
    
    with pytest.raises(ValidationError):
        ComparativeScore(
            a_better=True,
            b_better=True,
            tie=False,
            reasoning="impossible",
            confidence=0.9
        )


def test_binary_score_confidence_range():
    # Confidence too high
    with pytest.raises(ValidationError):
        BinaryScore(passed=True, reasoning="ok", confidence=1.1)

    # Valid confidence
    score = BinaryScore(passed=True, reasoning="ok", confidence=0.5)
    assert score.confidence == 0.5


def test_judge_config_defaults():
    config = JudgeConfig()
    assert config.model == "gpt-4o"
    assert config.mode == JudgeMode.RUBRIC
    assert config.temperature == 0.0
    assert config.max_retries == 3
