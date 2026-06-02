"""验证 EvalRunner 运行结束后会写入 aggregate_scores。"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.eval.runner import EvalRunner


@asynccontextmanager
async def _fake_session():
    yield MagicMock()


def _fake_factory():
    return _fake_session()


@pytest.mark.asyncio
async def test_runner_writes_aggregate_scores_after_completion():
    """跑完所有 case 后，最后一次 update_run 必须带 aggregate_scores。

    per-task session 模式：patch EvalStorage 让所有 storage 实例都是同一个
    mock，便于聚合 stub 的 get_results 返回 3 条 result，断言收尾的
    update_run 携带形状正确的 aggregate_scores。
    """
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

    cases = [
        MagicMock(id=uuid4(), case_key="q1", target_type="question",
                  input_json={}, golden_json=None),
    ]
    run_id = uuid4()

    with patch("app.eval.runner.EvalStorage", return_value=storage):
        runner = EvalRunner(_fake_factory, judge, fake_system_call)
        await runner.run(run_id, cases)

    # 找出收尾那一次（携带 aggregate_scores 的）update_run
    aggregate_calls = [
        c for c in storage.update_run.call_args_list
        if "aggregate_scores" in c.kwargs
    ]
    assert len(aggregate_calls) == 1, (
        f"应该恰好有 1 次带 aggregate_scores 的 update_run，实际 {len(aggregate_calls)}"
    )

    agg = aggregate_calls[0].kwargs["aggregate_scores"]
    assert "overall" in agg
    assert "by_target_type" in agg
    assert agg["by_target_type"]["question"]["avg"] == pytest.approx(7.0)
    assert agg["by_target_type"]["question"]["count"] == 2
    assert agg["by_target_type"]["scoring"]["avg"] == pytest.approx(7.0)
