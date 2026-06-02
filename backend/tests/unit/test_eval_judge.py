from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APITimeoutError

from app.eval.dimensions import JudgeMode
from app.eval.judge import BinaryJudge, ComparativeJudge, RubricJudge, SelfReflectionJudge
from app.eval.schemas import (
    BinaryScore,
    ComparativeScore,
    JudgeConfig,
    ReflectionScore,
    RubricDimensionScore,
    RubricJudgeScore,
)


@pytest.fixture
def judge_config():
    return JudgeConfig(model="gpt-4o", mode=JudgeMode.RUBRIC)


@pytest.mark.asyncio
async def test_rubric_judge_success(judge_config):
    judge = RubricJudge(judge_config)
    
    mock_score = RubricJudgeScore(
        target_type="question",
        dimensions=[
            RubricDimensionScore(dimension_name="relevance", score=8.0, reasoning="good")
        ],
        overall=8.0,
        reasoning="Overall good"
    )
    
    # Mock _evaluator_score pattern
    with patch.object(RubricJudge, "_chat_model") as mock_chat:
        mock_model = MagicMock()
        mock_runnable = AsyncMock()
        mock_runnable.ainvoke.return_value = mock_score
        mock_model.with_structured_output.return_value = mock_runnable
        mock_chat.return_value = mock_model
        
        # Mock reasoning stream
        with patch.object(RubricJudge, "_reasoning_stream", new_callable=AsyncMock):
            result = await judge.judge({"input": "query"}, {"output": "answer"})
            
            assert isinstance(result, RubricJudgeScore)
            assert result.overall == 8.0
            assert result.dimensions[0].dimension_name == "relevance"


@pytest.mark.asyncio
async def test_rubric_judge_fallback(judge_config):
    judge = RubricJudge(judge_config)
    
    with patch.object(RubricJudge, "_chat_model") as mock_chat:
        mock_model = MagicMock()
        mock_runnable = AsyncMock()
        # Mock unexpected output (not a RubricJudgeScore)
        mock_runnable.ainvoke.return_value = None
        mock_model.with_structured_output.return_value = mock_runnable
        mock_chat.return_value = mock_model
        
        with patch.object(RubricJudge, "_reasoning_stream", new_callable=AsyncMock):
            result = await judge.judge({"input": "query"}, {"output": "answer"})
            
            # Check fallback defaults
            assert isinstance(result, RubricJudgeScore)
            assert result.overall == 5.0
            assert "failed" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_comparative_judge(judge_config):
    judge_config.mode = JudgeMode.COMPARATIVE
    judge = ComparativeJudge(judge_config)
    
    mock_score = ComparativeScore(
        a_better=True,
        b_better=False,
        tie=False,
        reasoning="A is clearer",
        confidence=0.9
    )
    
    with patch.object(ComparativeJudge, "_chat_model") as mock_chat:
        mock_model = MagicMock()
        mock_runnable = AsyncMock()
        mock_runnable.ainvoke.return_value = mock_score
        mock_model.with_structured_output.return_value = mock_runnable
        mock_chat.return_value = mock_model
        
        result = await judge.judge({"input": "query"}, {"a": "output_a", "b": "output_b"})
        
        assert isinstance(result, ComparativeScore)
        assert result.a_better is True
        assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_binary_judge(judge_config):
    judge_config.mode = JudgeMode.BINARY
    judge = BinaryJudge(judge_config)
    
    mock_score = BinaryScore(
        passed=True,
        reasoning="Criteria met",
        confidence=0.95
    )
    
    with patch.object(BinaryJudge, "_chat_model") as mock_chat:
        mock_model = MagicMock()
        mock_runnable = AsyncMock()
        mock_runnable.ainvoke.return_value = mock_score
        mock_model.with_structured_output.return_value = mock_runnable
        mock_chat.return_value = mock_model
        
        result = await judge.judge({"input": "query"}, {"output": "answer"}, criteria="Must be polite")
        
        assert isinstance(result, BinaryScore)
        assert result.passed is True
        assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_self_reflection_judge(judge_config):
    inner_judge = RubricJudge(judge_config)
    judge = SelfReflectionJudge(inner_judge)
    
    mock_rubric_score = RubricJudgeScore(
        target_type="question",
        dimensions=[],
        overall=7.0,
        reasoning="Initial thought"
    )
    
    mock_reflection = ReflectionScore(
        original_confidence=0.7,
        adjusted=True,
        new_overall=8.0,
        reasoning="Actually it's better"
    )
    
    with patch.object(RubricJudge, "judge", new_callable=AsyncMock) as mock_inner_judge:
        mock_inner_judge.return_value = mock_rubric_score
        
        with patch.object(SelfReflectionJudge, "_reflect", new_callable=AsyncMock) as mock_reflect:
            mock_reflect.return_value = mock_reflection
            
            result = await judge.judge({"input": "query"}, {"output": "answer"})
            
            assert isinstance(result, ReflectionScore)
            assert result.adjusted is True
            assert result.new_overall == 8.0


@pytest.mark.asyncio
async def test_judge_retry(judge_config):
    judge = RubricJudge(judge_config)
    
    mock_score = RubricJudgeScore(
        target_type="question",
        dimensions=[],
        overall=8.0,
        reasoning="ok"
    )
    
    with patch.object(RubricJudge, "_chat_model") as mock_chat:
        mock_model = MagicMock()
        mock_runnable = AsyncMock()
        # First call fails, second succeeds
        mock_runnable.ainvoke.side_effect = [
            APITimeoutError(request=None), # Fixed initialization
            mock_score
        ]
        mock_model.with_structured_output.return_value = mock_runnable
        mock_chat.return_value = mock_model
        
        with patch.object(RubricJudge, "_reasoning_stream", new_callable=AsyncMock):
            result = await judge.judge({"input": "query"}, {"output": "answer"})
            assert result.overall == 8.0

    # Verify the retry decorator works on _rubric_score via _chat_model mock.


@pytest.mark.asyncio
async def test_reasoning_stream_retries_on_rate_limit(judge_config):
    """_reasoning_stream 遇到 RateLimitError 必须重试而不是直接 fallback。"""
    from openai import RateLimitError

    judge = RubricJudge(judge_config)

    mock_score = RubricJudgeScore(
        target_type="question",
        dimensions=[
            RubricDimensionScore(dimension_name="relevance", score=8.0, reasoning="ok")
        ],
        overall=8.0,
        reasoning="good",
    )

    stream_attempt = 0
    chat_calls = []

    def flaky_astream(messages):
        nonlocal stream_attempt
        stream_attempt += 1
        if stream_attempt < 3:
            raise RateLimitError(
                "rate limit",
                response=MagicMock(status_code=429),
                body=None,
            )

        async def _gen():
            yield "ok"

        return _gen()

    def side_effect_chat_model(streaming=False):
        chat_calls.append(streaming)
        model = MagicMock()
        if streaming:
            model.with_config = MagicMock(return_value=model)
            model.astream = flaky_astream
        else:
            runnable = AsyncMock()
            runnable.ainvoke.return_value = mock_score
            model.with_structured_output = MagicMock(return_value=runnable)
        return model

    with patch.object(RubricJudge, "_chat_model", side_effect=side_effect_chat_model):
        result = await judge.judge({"input": "query"}, {"output": "answer"})

    assert result.overall == 8.0, (
        f"重试成功应返回 overall=8.0，实际 {result.overall}"
    )
    assert stream_attempt == 3, (
        f"期望 _reasoning_stream 被调用 3 次（前 2 次 429 重试），实际 {stream_attempt} 次"
    )
