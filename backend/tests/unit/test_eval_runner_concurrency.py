"""验证 EvalRunner 在并发跑 case 时使用 per-task AsyncSession。

历史背景：S6 全量评测出现 InvalidRequestError / PendingRollbackError，
根因是所有 case 共享同一 AsyncSession（SQLAlchemy AsyncSession 不是协程安全的）。
修复方案：每个并发 task 从 session_factory 拿自己的 session。
不要采用"对 DB 操作加串行锁"——那等于把并发退化为串行，且 race 仍可能从其它路径漏出。
"""
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.eval.runner import EvalRunner


@asynccontextmanager
async def _recording_session_factory(record: list):
    """每次被调用都 yield 一个新 MagicMock，并把 session id 记入 record。"""
    session = MagicMock(name=f"session_{len(record)}")
    record.append(session)
    yield session


def _make_factory(record: list):
    def factory():
        return _recording_session_factory(record)
    return factory


def _build_judge() -> MagicMock:
    judge = MagicMock()
    judge.judge = AsyncMock(return_value=MagicMock(
        model_dump=lambda: {"overall": 7.0},
        reasoning="r",
        overall=7.0,
        passed=True,
    ))
    return judge


def _build_storage_factory():
    """每次 EvalStorage(session) 都返回一个新 mock storage（不同实例）。"""
    def make(session):
        s = MagicMock()
        s.bound_session = session  # 留痕用，便于断言
        s.update_run = AsyncMock()
        s.save_result = AsyncMock()
        s.get_run = AsyncMock(return_value=MagicMock(completed_cases=0))
        s.get_results = AsyncMock(return_value=[])
        return s
    return make


@pytest.mark.asyncio
async def test_runner_uses_separate_session_per_case():
    """并发跑 3 个 case 时，每个 case 必须从 session_factory 拿到自己的 session。"""
    sessions: list = []
    judge = _build_judge()

    async def fake_system_call(tt, inp):
        # 加一点 sleep 制造真实并发窗口
        await asyncio.sleep(0.01)
        return {"answer": "x"}

    with patch("app.eval.runner.EvalStorage", side_effect=_build_storage_factory()):
        runner = EvalRunner(_make_factory(sessions), judge, fake_system_call,
                            max_concurrency=3)
        cases = [
            MagicMock(id=uuid4(), case_key=f"c{i}", target_type="question",
                      input_json={}, golden_json=None)
            for i in range(3)
        ]
        await runner.run(uuid4(), cases)

    # 至少：1 起跑 session + 3 case session + 1 收尾聚合 session = 5
    # 取 ≥4 保留一点宽容（如果未来 runner 把起跑与聚合合到主 session 之类的微调）
    assert len(sessions) >= 4, (
        f"per-task session 模式要求每个 case 都拿独立 session，实际 factory 只被调用 "
        f"{len(sessions)} 次。如果用了共享 session 或串行锁方案，本测试就该失败。"
    )

    # 每次 factory 调用产出的必须是不同实例
    unique_ids = {id(s) for s in sessions}
    assert len(unique_ids) == len(sessions), \
        "session_factory 必须每次产出新实例，不能复用同一 session 对象"


@pytest.mark.asyncio
async def test_runner_isolates_case_failures_between_tasks():
    """一个 case 抛错时，其它 case 仍能继续跑完（独立 session 互不污染）。"""
    sessions: list = []
    judge = _build_judge()

    call_log: list[str] = []

    async def flaky_system_call(tt, inp):
        case_key = inp.get("_case_key", "?")
        call_log.append(case_key)
        if case_key == "c0":
            raise RuntimeError("simulated case failure")
        return {"answer": "ok"}

    cases = [
        MagicMock(id=uuid4(), case_key=f"c{i}", target_type="question",
                  input_json={"_case_key": f"c{i}"}, golden_json=None)
        for i in range(3)
    ]

    with patch("app.eval.runner.EvalStorage", side_effect=_build_storage_factory()):
        runner = EvalRunner(_make_factory(sessions), judge, flaky_system_call,
                            max_concurrency=3)
        # 不应整体崩
        await runner.run(uuid4(), cases)

    # 失败的 c0 + 成功的 c1/c2 都被调用了
    assert "c0" in call_log
    assert "c1" in call_log
    assert "c2" in call_log


@pytest.mark.asyncio
async def test_runner_retries_system_call_on_rate_limit():
    """system_call 遇到 OpenAI RateLimitError 时自动重试。"""
    from openai import RateLimitError

    sessions: list = []
    judge = _build_judge()

    call_count = 0

    async def flaky_system_call(tt, inp):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RateLimitError(
                "rate limit",
                response=MagicMock(status_code=429),
                body=None,
            )
        return {"answer": "ok"}

    with patch("app.eval.runner.EvalStorage", side_effect=_build_storage_factory()):
        runner = EvalRunner(_make_factory(sessions), judge, flaky_system_call,
                            max_concurrency=1)
        cases = [
            MagicMock(id=uuid4(), case_key="c0", target_type="question",
                      input_json={}, golden_json=None),
        ]
        await runner.run(uuid4(), cases)

    # 前 2 次失败被重试，第 3 次成功
    assert call_count == 3, (
        f"期望 system_call 被重试 3 次才成功，实际调用了 {call_count} 次"
    )


@pytest.mark.asyncio
async def test_runner_completed_cases_exact_after_concurrent_run():
    """并发 3 个成功 case 后 completed_cases 必须精确为 3。"""
    sessions: list = []

    async def fake_system_call(tt, inp):
        return {"answer": "ok"}

    counter = {"value": 0}

    def _make_storage_by_session(session):
        s = MagicMock()
        s.bound_session = session
        s.update_run = AsyncMock()
        s.save_result = AsyncMock()

        async def fake_increment(run_id):
            counter["value"] += 1

        s.increment_completed_cases = fake_increment
        s.get_run = AsyncMock(return_value=MagicMock(completed_cases=0))
        s.get_results = AsyncMock(return_value=[])
        return s

    with patch("app.eval.runner.EvalStorage", side_effect=_make_storage_by_session):
        runner = EvalRunner(
            _make_factory(sessions),
            _build_judge(),
            fake_system_call,
            max_concurrency=3,
        )
        cases = [
            MagicMock(id=uuid4(), case_key=f"c{i}", target_type="question",
                      input_json={}, golden_json=None)
            for i in range(3)
        ]
        await runner.run(uuid4(), cases)

    assert counter["value"] == 3, (
        f"并发 3 个成功 case 后期望 completed_cases=3，实际 {counter['value']}"
    )


@pytest.mark.asyncio
async def test_runner_binary_pass_maps_from_overall_score():
    """binary_pass 应该从 overall_score 显式计算，overall >= 7.0 为 True。"""
    sessions: list = []
    judge = _build_judge()

    saved_results = []

    def _make_storage_by_session(session):
        s = MagicMock()
        s.bound_session = session
        s.update_run = AsyncMock()
        s.increment_completed_cases = AsyncMock()

        async def fake_save_result(result_data):
            saved_results.append(result_data)

        s.save_result = fake_save_result
        s.get_run = AsyncMock(return_value=MagicMock(completed_cases=0))
        s.get_results = AsyncMock(return_value=[])
        return s

    async def fake_system_call(tt, inp):
        return {"answer": "ok"}

    with patch("app.eval.runner.EvalStorage", side_effect=_make_storage_by_session):
        runner = EvalRunner(
            _make_factory(sessions),
            judge,
            fake_system_call,
            max_concurrency=1,
        )
        cases = [
            MagicMock(id=uuid4(), case_key="c0", target_type="question",
                      input_json={}, golden_json=None),
        ]
        await runner.run(uuid4(), cases)

    assert len(saved_results) == 1
    assert saved_results[0]["binary_pass"] is True, (
        f"overall=7.0 期望 binary_pass=True，实际 {saved_results[0]['binary_pass']}"
    )


@pytest.mark.asyncio
async def test_runner_binary_pass_false_when_below_threshold():
    """overall < 7.0 时 binary_pass 应为 False。"""
    sessions: list = []
    judge = MagicMock()
    judge.judge = AsyncMock(return_value=MagicMock(
        model_dump=lambda: {"overall": 5.0},
        reasoning="r",
        overall=5.0,
    ))

    saved_results = []

    def _make_storage_by_session(session):
        s = MagicMock()
        s.bound_session = session
        s.update_run = AsyncMock()
        s.increment_completed_cases = AsyncMock()

        async def fake_save_result(result_data):
            saved_results.append(result_data)

        s.save_result = fake_save_result
        s.get_run = AsyncMock(return_value=MagicMock(completed_cases=0))
        s.get_results = AsyncMock(return_value=[])
        return s

    async def fake_system_call(tt, inp):
        return {"answer": "ok"}

    with patch("app.eval.runner.EvalStorage", side_effect=_make_storage_by_session):
        runner = EvalRunner(
            _make_factory(sessions),
            judge,
            fake_system_call,
            max_concurrency=1,
        )
        cases = [
            MagicMock(id=uuid4(), case_key="c0", target_type="question",
                      input_json={}, golden_json=None),
        ]
        await runner.run(uuid4(), cases)

    assert len(saved_results) == 1
    assert saved_results[0]["binary_pass"] is False


@pytest.mark.asyncio
async def test_judge_semaphore_initialized():
    """judge semaphore 必须正确初始化，默认值为 max(1, max_concurrency // 2)。"""
    sessions: list = []

    with patch("app.eval.runner.EvalStorage", side_effect=_build_storage_factory()):
        runner = EvalRunner(
            _make_factory(sessions),
            _build_judge(),
            AsyncMock(return_value={"answer": "ok"}),
            max_concurrency=5,
        )

    assert runner._judge_semaphore is not None
    assert runner._judge_semaphore._value == 2  # max(1, 5 // 2) = 2


@pytest.mark.asyncio
async def test_judge_semaphore_configurable():
    """judge_max_concurrency 应可显式配置。"""
    sessions: list = []

    with patch("app.eval.runner.EvalStorage", side_effect=_build_storage_factory()):
        runner = EvalRunner(
            _make_factory(sessions),
            _build_judge(),
            AsyncMock(return_value={"answer": "ok"}),
            max_concurrency=5,
            judge_max_concurrency=3,
        )

    assert runner._judge_semaphore._value == 3
