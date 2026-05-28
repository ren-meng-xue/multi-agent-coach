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
