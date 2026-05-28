"""验证 EvalRunner 失败 case 使用 structlog 而非 print。"""
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
async def test_runner_logs_via_structlog_on_case_failure(capsys):
    storage = MagicMock()
    storage.update_run = AsyncMock()
    storage.save_result = AsyncMock()
    storage.get_run = AsyncMock(return_value=MagicMock(completed_cases=0))
    storage.get_results = AsyncMock(return_value=[])

    judge = MagicMock()

    async def broken_system_call(tt, inp):
        raise RuntimeError("simulated crash")

    cases = [
        MagicMock(id=uuid4(), case_key="c1", target_type="question",
                  input_json={}, golden_json=None),
    ]
    with patch("app.eval.runner.EvalStorage", return_value=storage), \
         patch("app.eval.runner.log") as mock_log:
        runner = EvalRunner(_fake_factory, judge, broken_system_call)
        await runner.run(uuid4(), cases)
        assert mock_log.error.called or mock_log.warning.called

    captured = capsys.readouterr()
    assert "Error running case" not in captured.out
