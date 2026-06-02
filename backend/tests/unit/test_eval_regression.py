"""验证 RegressionTester.compare_runs 写入 EvalComparison。"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.eval.regression import RegressionTester


@pytest.mark.asyncio
async def test_compare_runs_writes_eval_comparison_rows():
    storage = MagicMock()
    storage.get_results = AsyncMock(side_effect=[
        [
            MagicMock(case_key="q1", target_type="question", overall_score=6.0),
            MagicMock(case_key="s1", target_type="scoring", overall_score=7.0),
        ],
        [
            MagicMock(case_key="q1", target_type="question", overall_score=8.0),
            MagicMock(case_key="s1", target_type="scoring", overall_score=7.2),
        ],
    ])
    storage.get_run = AsyncMock(return_value=MagicMock(suite=MagicMock(name="interviewer_v0")))
    storage.save_comparison = AsyncMock()

    tester = RegressionTester(storage)
    out = await tester.compare_runs(uuid4(), uuid4())

    assert "improved" in out
    assert "degraded" in out
    assert "stable" in out

    assert storage.save_comparison.await_count >= 1
    called_args_list = [c.args[0] for c in storage.save_comparison.call_args_list]
    metrics = [c.get("metric") for c in called_args_list]
    assert "question" in metrics
    q_row = next(c for c in called_args_list if c["metric"] == "question")
    assert q_row["winner"] == "b"
    assert q_row["significant"] is True
    assert q_row["delta"] == pytest.approx(2.0)
