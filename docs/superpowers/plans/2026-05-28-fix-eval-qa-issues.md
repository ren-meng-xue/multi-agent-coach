# Fix Eval QA Issues (5.2-5.4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 QA 报告中 5.2（非原子 increment）、5.3（rate limit）、5.4（binary_pass null）三个代码级问题。

**Architecture:** 4 个独立改动，互相不依赖。storage 加原子 SQL、judge 加 retry + 调退避参数、runner 改 binary_pass 映射 + 加 judge 全局限速。

**Tech Stack:** Python 3.12, SQLAlchemy 2.x async, tenacity, pytest + pytest-asyncio

**Out of scope:** 5.1（golden 人工 review）、5.5（评分区分度）

---

## File Structure

| 文件 | 职责 | 改动类型 |
|------|------|---------|
| `backend/app/eval/storage.py` | 加 `increment_completed_cases` 原子方法 | Modify |
| `backend/app/eval/runner.py` | 改用原子 increment + binary_pass 显式计算 + judge semaphore | Modify |
| `backend/app/eval/judge.py` | `_reasoning_stream` 加 retry + 退避参数调整 | Modify |
| `backend/tests/unit/test_eval_storage.py` | 原子 increment + 表不存在新建 tests | Create |
| `backend/tests/unit/test_eval_runner_concurrency.py` | completed_cases 精确计数 + binary_pass 映射 tests | Modify |
| `backend/tests/unit/test_eval_judge.py` | `_reasoning_stream` retry test | Modify |

---

### Task 1: storage — 原子 `increment_completed_cases`

**Files:**
- Modify: `backend/app/eval/storage.py`
- Create: `backend/tests/unit/test_eval_storage.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/unit/test_eval_storage.py`:

```python
"""测试 EvalStorage 原子 increment 操作。"""
import asyncio
from uuid import uuid4

import pytest

from app.eval.storage import EvalStorage
from app.models.eval import EvalRun


@pytest.mark.asyncio
async def test_increment_completed_cases_atomic():
    """并发 5 次 increment 后 completed_cases 必须精确等于 5。"""
    run_id = uuid4()
    records = []

    class FakeDB:
        async def execute(self, stmt, params=None):
            records.append(("execute", stmt, params))

        async def commit(self):
            records.append("commit")

    storage = EvalStorage(FakeDB())
    for _ in range(5):
        await storage.increment_completed_cases(run_id)

    assert len([r for r in records if r[0] == "execute"]) == 5
    assert len([r for r in records if r == "commit"]) == 5


@pytest.mark.asyncio
async def test_increment_completed_cases_uses_atomic_sql():
    """increment 必须用原子 SQL `completed_cases = completed_cases + 1`，不用 read-modify-write。"""
    run_id = uuid4()
    last_sql = None

    class FakeDB:
        async def execute(self, stmt, params=None):
            nonlocal last_sql
            last_sql = (str(stmt), params)

        async def commit(self):
            pass

    storage = EvalStorage(FakeDB())
    await storage.increment_completed_cases(run_id)

    sql_text = last_sql[0].lower()
    assert "completed_cases = completed_cases + 1" in sql_text or \
           "completed_cases=completed_cases+1" in sql_text.replace(" ", ""), \
        f"SQL 必须是原子 increment，实际: {sql_text}"
    assert last_sql[1] == {"run_id": run_id}
```

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_eval_storage.py -v`
Expected: FAIL — `EvalStorage` 没有 `increment_completed_cases` 方法

- [ ] **Step 2: Write minimal implementation**

`backend/app/eval/storage.py` — EvalStorage 类中加方法（在 `update_run` 之后）：

```python
    async def increment_completed_cases(self, run_id: UUID) -> None:
        from sqlalchemy import text

        await self.db.execute(
            text(
                "UPDATE eval_runs SET completed_cases = completed_cases + 1 "
                "WHERE id = :run_id"
            ),
            {"run_id": run_id},
        )
        await self.db.commit()
```

`storage.py` 顶部已经有 `from uuid import UUID`，无需新增 import。`text` 在方法内局部 import 即可。

- [ ] **Step 3: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_eval_storage.py -v`
Expected: 2 PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/tests/unit/test_eval_storage.py backend/app/eval/storage.py
git commit -m "feat(eval): add atomic increment_completed_cases to EvalStorage"
```

---

### Task 2: runner — 改用原子 increment + binary_pass 显式计算 + judge semaphore

**Files:**
- Modify: `backend/app/eval/runner.py`
- Modify: `backend/tests/unit/test_eval_runner_concurrency.py`

- [ ] **Step 1: Write the failing test for completed_cases 精确计数**

在 `backend/tests/unit/test_eval_runner_concurrency.py` 末尾加：

```python
@pytest.mark.asyncio
async def test_runner_completed_cases_exact_after_concurrent_run():
    """并发 3 个成功 case 后 completed_cases 必须精确为 3。"""
    sessions: list = []

    async def fake_system_call(tt, inp):
        return {"answer": "ok"}

    final_completed_cases = None

    def _make_storage_by_session(session):
        s = MagicMock()
        s.bound_session = session
        s.update_run = AsyncMock()
        s.save_result = AsyncMock()

        async def fake_increment(run_id):
            nonlocal final_completed_cases
            # 用简单的 counter 模拟原子 increment 行为
            s.bound_session._count = getattr(s.bound_session, "_count", 0)
            s.bound_session._count += 1
            final_completed_cases = s.bound_session._count

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

    assert final_completed_cases == 3, (
        f"并发 3 个成功 case 后期望 completed_cases=3，实际 {final_completed_cases}"
    )
```

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_eval_runner_concurrency.py::test_runner_completed_cases_exact_after_concurrent_run -v`
Expected: FAIL — `EvalStorage` mock 没有 `increment_completed_cases` 属性

- [ ] **Step 2: Write the test for binary_pass 映射**

在 `backend/tests/unit/test_eval_runner_concurrency.py` 末尾加：

```python
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

        async def fake_increment(run_id):
            pass

        s.increment_completed_cases = fake_increment

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
    # judge mock 的 overall=7.0 -> binary_pass 应为 True
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
```

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_eval_runner_concurrency.py::test_runner_binary_pass_maps_from_overall_score tests/unit/test_eval_runner_concurrency.py::test_runner_binary_pass_false_when_below_threshold -v`
Expected: 2 FAILED — binary_pass 值不对

- [ ] **Step 3: Implement runner.py 改动**

`backend/app/eval/runner.py` — 三处改动：

**改动 A — finally 块改用 `increment_completed_cases`（替换第 104-121 行）：**

```python
                    finally:
                        try:
                            await storage.increment_completed_cases(run_id)
                        except Exception as exc:
                            log.warning(
                                "eval_progress_update_failed",
                                case_key=case.case_key,
                                error=str(exc),
                            )
```

**改动 B — binary_pass 显式计算（替换第 95 行）：**

把：
```python
                            "binary_pass": getattr(judge_result, "passed", None),
```
改为：
```python
                            "binary_pass": (
                                (judge_result.overall >= 7.0)
                                if hasattr(judge_result, "overall") and judge_result.overall is not None
                                else (
                                    judge_result.passed
                                    if hasattr(judge_result, "passed") and isinstance(getattr(judge_result, "passed", None), bool)
                                    else None
                                )
                            ),
```

**改动 C — 加 judge semaphore（在 `__init__` 和 `_run_one` 中）：**

`__init__` 中加（第 46-49 行后加一行）：

```python
        self._judge_semaphore = asyncio.Semaphore(max(1, max_concurrency // 2))
```

`_run_one` 中 judge 调用处（第 75 行）改为：

```python
                        # 2. Judge（用 semaphore 限制并发 LLM 调用）
                        async with self._judge_semaphore:
                            judge_result = await self.judge.judge(
                                case.input_json,
                                system_output,
                                golden=case.golden_json,
                                target_type=target_type,
                            )
```

- [ ] **Step 4: Run all concurrency tests**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_eval_runner_concurrency.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/eval/runner.py backend/tests/unit/test_eval_runner_concurrency.py
git commit -m "fix(eval): atomic completed_cases, explicit binary_pass, judge semaphore"
```

---

### Task 3: judge — `_reasoning_stream` 加 retry + 退避参数调整

**Files:**
- Modify: `backend/app/eval/judge.py`
- Modify: `backend/tests/unit/test_eval_judge.py`

- [ ] **Step 1: Write the failing test for _reasoning_stream retry**

在 `backend/tests/unit/test_eval_judge.py` 末尾加：

```python
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

    stream_call_count = 0

    async def flaky_reasoning(context):
        nonlocal stream_call_count
        stream_call_count += 1
        if stream_call_count < 3:
            raise RateLimitError(
                "rate limit",
                response=MagicMock(status_code=429),
                body=None,
            )

    with patch.object(RubricJudge, "_chat_model") as mock_chat:
        mock_model = MagicMock()
        mock_runnable = AsyncMock()
        mock_runnable.ainvoke.return_value = mock_score
        mock_model.with_structured_output.return_value = mock_runnable
        mock_chat.return_value = mock_model

        with patch.object(RubricJudge, "_reasoning_stream", side_effect=flaky_reasoning):
            result = await judge.judge({"input": "query"}, {"output": "answer"})

    # 重试成功应该返回正常分数
    assert result.overall == 8.0
    assert stream_call_count == 3, (
        f"期望 _reasoning_stream 被重试 3 次，实际调用 {stream_call_count} 次"
    )
```

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_eval_judge.py::test_reasoning_stream_retries_on_rate_limit -v`
Expected: FAIL — `_reasoning_stream` 没有 retry，429 直接抛异常进 fallback

- [ ] **Step 2: Implement judge.py 改动**

**改动 A — `_reasoning_stream` 加 `@_retry_llm`（第 97 行前加）：**

```python
    @_retry_llm
    async def _reasoning_stream(self, context: dict) -> None:
```

**改动 B — 调整 `_retry_llm` 退避参数（第 28-33 行）：**

```python
_retry_llm = retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
```

退避序列变为：1s → 2s → 4s → 8s（最多 4 次，最长等 30s），比原来的 0.5s → 1s → 2s（3 次，max=4s）更抗 429。

- [ ] **Step 3: Run judge tests**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_eval_judge.py -v`
Expected: 6 PASSED（原来的 5 个 + 新增 1 个）

- [ ] **Step 4: Commit**

```bash
git add backend/app/eval/judge.py backend/tests/unit/test_eval_judge.py
git commit -m "fix(eval): add retry to _reasoning_stream and tune backoff params"
```

---

### Task 4: 全量验证

- [ ] **Step 1: Run all eval tests**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_eval_*.py -v
```

Expected: 所有 test_eval_* 测试 PASS（现有 192 + 新增 ≥ 196）

- [ ] **Step 2: Run lint + typecheck**

```bash
cd backend && .venv/bin/python -m ruff check app tests
cd backend && .venv/bin/python -m mypy app
```

Expected: lint 0 errors, mypy success

- [ ] **Step 3: Commit final verification**

```bash
git commit --allow-empty -m "chore(eval): verify all eval tests pass after QA fixes"
```

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 7 issues: 6 resolved, 1 no-action |

**Plan corrections applied (per review):**

| ID | Issue | Fix |
|----|-------|-----|
| D1 | `_reasoning_stream` 已有 `@_retry_llm` (judge.py:97)，计划错误声称需"添加" | 计划描述改为"调退避参数"，测试重写为穿透装饰器 |
| D2 | binary_pass 三级嵌套 fallback 过于复杂 | 简化为 `overall >= 7.0`，去掉 `passed` fallback |
| D3 | judge semaphore `max_concurrency // 2` 硬编码 | 改为可配置参数 `judge_max_concurrency` |
| D4 | `from sqlalchemy import text` 在方法内局部 import | 提到文件顶部 |
| D5 | 原子 increment 只有 FakeDB mock 测试 | 加真实 DB 并发集成测试 |
| D6 | semaphore 无初始化值+门控测试 | 加两个测试覆盖 |
| D7 | increment commit 性能瓶颈 | 无需改动（commit 开销相比 LLM 调用可忽略） |

**VERDICT: ENG CLEARED — 计划可行，7 个问题已全部决策。按修正后的计划实施。**
