"""验证 EvalRunner 运行结束后会写入 aggregate_scores。"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.eval.runner import EvalRunner


@pytest.mark.asyncio
async def test_runner_writes_aggregate_scores_after_completion():
    storage = MagicMock()
    storage.update_run = AsyncMock()
    storage.save_result = AsyncMock()
    storage.get_run = AsyncMock(return_value=MagicMock(completed_cases=0))
    storage.get_results = AsyncMock(return_value=[
        MagicMock(target_type="question", overall_score=8.0, binary_pass=True),
        MagicMock(target_type="question", overall_score=6.0, binary_pass=False),
        MagicMock(target_type="scoring", overall_score=7.0, binary_pass=True),
    ])

    judge = MagicMock()
    judge.judge = AsyncMock(return_value=MagicMock(
        model_dump=lambda: {"overall": 7.0},
        reasoning="r",
        overall=7.0,
        passed=True,
    ))

    async def fake_system_call(tt, inp):
        return {"answer": "x"}

    runner = EvalRunner(storage, judge, fake_system_call)
    cases = [
        MagicMock(id=uuid4(), case_key="q1", target_type="question", input_json={}, golden_json=None),
    ]
    run_id = uuid4()
    await runner.run(run_id, cases)

    final_call = storage.update_run.call_args_list[-1]
    kwargs = final_call.kwargs
    assert "aggregate_scores" in kwargs
    agg = kwargs["aggregate_scores"]
    assert "overall" in agg
    assert "by_target_type" in agg
    assert agg["by_target_type"]["question"]["avg"] == pytest.approx(7.0)
    assert agg["by_target_type"]["question"]["count"] == 2
    assert agg["by_target_type"]["scoring"]["avg"] == pytest.approx(7.0)
