"""EvalRunner：并发跑 eval case，每个 case 在自己的 AsyncSession 里。

为什么不共享 session：SQLAlchemy AsyncSession 不是协程安全的。
当 max_concurrency > 1 时，多协程同时 commit/rollback 会撞
InvalidRequestError / PendingRollbackError（S6 全量跑时实测过）。
解法是 per-task session：每个并发单元从 session_factory 拿一个新的。
"""
import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.eval.dimensions import TargetType
from app.eval.judge import BaseJudge
from app.eval.storage import EvalStorage

SystemCall = Callable[[TargetType, dict[str, Any]], Awaitable[dict[str, Any]]]
SessionFactory = Callable[[], AbstractAsyncContextManager[Any]]

log = get_logger("app.eval.runner")

_SYSTEM_RETRYABLE = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)

_system_retry = retry(
    retry=retry_if_exception_type(_SYSTEM_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=8),
    reraise=True,
)


class EvalRunner:
    def __init__(
        self,
        session_factory: SessionFactory,
        judge: BaseJudge,
        system_call: SystemCall,
        max_concurrency: int = 5,
        judge_max_concurrency: int | None = None,
    ):
        self.session_factory = session_factory
        self.judge = judge
        self.system_call = system_call
        self.max_concurrency = max_concurrency
        self._judge_semaphore = asyncio.Semaphore(
            judge_max_concurrency
            if judge_max_concurrency is not None
            else max(1, max_concurrency // 2)
        )

    async def run(self, run_id: UUID, cases: list[Any]) -> None:
        semaphore = asyncio.Semaphore(self.max_concurrency)

        # 起跑：在自己的 session 里把 status 置 running
        async with self.session_factory() as session:
            storage = EvalStorage(session)
            await storage.update_run(
                run_id, status="running", started_at=datetime.now(UTC)
            )

        async def _run_one(case: Any) -> None:
            # 每个 case 在自己的 session 里执行，避免共享 AsyncSession 并发崩
            async with semaphore, self.session_factory() as session:
                    storage = EvalStorage(session)
                    start_time = datetime.now(UTC).timestamp()
                    try:
                        target_type = TargetType(case.target_type)
                        # 1. System output：调真实 Agent 节点（带 rate limit 重试）
                        @_system_retry
                        async def _do_system_call():
                            return await self.system_call(target_type, case.input_json)

                        system_output = await _do_system_call()
                        latency = int(
                            (datetime.now(UTC).timestamp() - start_time) * 1000
                        )

                        # 2. Judge（用 semaphore 限制并发 LLM 调用）
                        async with self._judge_semaphore:
                            judge_result = await self.judge.judge(
                                case.input_json,
                                system_output,
                                golden=case.golden_json,
                                target_type=target_type,
                            )

                        # 3. Save
                        await storage.save_result({
                            "run_id": run_id,
                            "case_id": case.id,
                            "case_key": case.case_key,
                            "target_type": case.target_type,
                            "system_output": system_output,
                            "judge_scores": (
                                judge_result.model_dump()
                                if hasattr(judge_result, "model_dump") else {}
                            ),
                            "judge_reasoning": getattr(judge_result, "reasoning", ""),
                            "overall_score": getattr(judge_result, "overall", None),
                            "binary_pass": (
                                (judge_result.overall >= 7.0)
                                if hasattr(judge_result, "overall") and judge_result.overall is not None
                                else None
                            ),
                            "latency_ms": latency,
                        })
                    except Exception as e:
                        log.error(
                            "eval_case_failed",
                            case_key=case.case_key,
                            error=str(e),
                        )
                    finally:
                        try:
                            await storage.increment_completed_cases(run_id)
                        except Exception as exc:
                            log.warning(
                                "eval_progress_update_failed",
                                case_key=case.case_key,
                                error=str(exc),
                            )

        await asyncio.gather(*(_run_one(c) for c in cases))

        # 收尾：用自己的 session 聚合结果 + 标记完成
        async with self.session_factory() as session:
            storage = EvalStorage(session)
            results = await storage.get_results(run_id)
            stats: dict[str, dict[str, float]] = {}
            for r in results:
                t = r.target_type
                if t not in stats:
                    stats[t] = {"sum": 0.0, "pass": 0.0, "count": 0.0}
                stats[t]["sum"] += float(r.overall_score or 0.0)
                if r.binary_pass:
                    stats[t]["pass"] += 1.0
                stats[t]["count"] += 1.0

            by_target_type = {
                t: {
                    "avg": v["sum"] / v["count"] if v["count"] > 0 else 0.0,
                    "pass_rate": v["pass"] / v["count"] if v["count"] > 0 else 0.0,
                    "count": int(v["count"]),
                }
                for t, v in stats.items()
            }
            overall = (
                sum(v["avg"] for v in by_target_type.values()) / len(by_target_type)
                if by_target_type
                else 0.0
            )
            aggregate_scores = {"overall": overall, "by_target_type": by_target_type}

            await storage.update_run(
                run_id,
                aggregate_scores=aggregate_scores,
                status="completed",
                completed_at=datetime.now(UTC),
            )
