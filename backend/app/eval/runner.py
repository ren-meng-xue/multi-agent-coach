import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.eval.dimensions import TargetType
from app.eval.judge import BaseJudge
from app.eval.storage import EvalStorage

SystemCall = Callable[[TargetType, dict[str, Any]], Awaitable[dict[str, Any]]]


class EvalRunner:
    def __init__(
        self,
        storage: EvalStorage,
        judge: BaseJudge,
        system_call: SystemCall,
        max_concurrency: int = 5,
    ):
        self.storage = storage
        self.judge = judge
        self.system_call = system_call
        self.max_concurrency = max_concurrency

    async def run(self, run_id, cases):
        semaphore = asyncio.Semaphore(self.max_concurrency)
        tasks = []
        
        await self.storage.update_run(run_id, status="running", started_at=datetime.now(UTC))

        async def _run_one(case):
            async with semaphore:
                start_time = datetime.now(UTC).timestamp()
                try:
                    target_type = TargetType(case.target_type)
                    # 1. System output：调真实 Agent 节点
                    system_output = await self.system_call(target_type, case.input_json)
                    latency = int((datetime.now(UTC).timestamp() - start_time) * 1000)

                    # 2. Judge
                    judge_result = await self.judge.judge(
                        case.input_json, system_output, golden=case.golden_json, target_type=target_type
                    )

                    # 3. Save
                    await self.storage.save_result({
                        "run_id": run_id,
                        "case_id": case.id,
                        "case_key": case.case_key,
                        "target_type": case.target_type,
                        "system_output": system_output,
                        "judge_scores": judge_result.model_dump() if hasattr(judge_result, "model_dump") else {},
                        "judge_reasoning": getattr(judge_result, "reasoning", ""),
                        "overall_score": getattr(judge_result, "overall", None),
                        "binary_pass": getattr(judge_result, "passed", None),
                        "latency_ms": latency,
                    })
                except Exception as e:
                    print(f"Error running case {case.case_key}: {e}")
                finally:
                    # Increment completed cases
                    run = await self.storage.get_run(run_id)
                    if run:
                        await self.storage.update_run(run_id, completed_cases=run.completed_cases + 1)

        for case in cases:
            tasks.append(_run_one(case))
        
        await asyncio.gather(*tasks)
        results = await self.storage.get_results(run_id)
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

        await self.storage.update_run(
            run_id,
            aggregate_scores=aggregate_scores,
            status="completed",
            completed_at=datetime.now(UTC),
        )
