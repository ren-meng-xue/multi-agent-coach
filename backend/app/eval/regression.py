from typing import Any
from uuid import UUID

from app.eval.storage import EvalStorage

SIGNIFICANCE_DELTA = 0.5


class RegressionTester:
    def __init__(self, storage: EvalStorage):
        self.storage = storage

    async def compare_runs(self, run_a_id: UUID, run_b_id: UUID) -> dict[str, Any]:
        results_a = await self.storage.get_results(run_a_id)
        results_b = await self.storage.get_results(run_b_id)
        
        # Simple comparison logic
        # Map by case_key
        map_a = {r.case_key: r for r in results_a}
        map_b = {r.case_key: r for r in results_b}
        
        common_keys = set(map_a.keys()) & set(map_b.keys())
        
        comparison: dict[str, Any] = {
            "total_cases": len(common_keys),
            "improved": [],
            "degraded": [],
            "stable": []
        }
        
        for key in common_keys:
            score_a = map_a[key].overall_score or 0.0
            score_b = map_b[key].overall_score or 0.0
            
            diff = score_b - score_a
            if diff > SIGNIFICANCE_DELTA:
                comparison["improved"].append(key)
            elif diff < -SIGNIFICANCE_DELTA:
                comparison["degraded"].append(key)
            else:
                comparison["stable"].append(key)

        run_a = await self.storage.get_run(run_a_id)
        suite_name = run_a.suite.name if run_a and run_a.suite else "unknown"

        def _avg_by_type(results):
            stats: dict[str, dict[str, float]] = {}
            for r in results:
                t = r.target_type
                if t not in stats:
                    stats[t] = {"sum": 0.0, "count": 0.0}
                stats[t]["sum"] += float(r.overall_score or 0.0)
                stats[t]["count"] += 1.0
            return {
                t: (v["sum"] / v["count"] if v["count"] > 0 else 0.0)
                for t, v in stats.items()
            }

        avg_a = _avg_by_type(results_a)
        avg_b = _avg_by_type(results_b)
        common_types = set(avg_a) & set(avg_b)

        for target_type in sorted(common_types):
            score_a = avg_a[target_type]
            score_b = avg_b[target_type]
            delta = score_b - score_a
            significant = abs(delta) > SIGNIFICANCE_DELTA
            if delta > SIGNIFICANCE_DELTA:
                winner = "b"
            elif delta < -SIGNIFICANCE_DELTA:
                winner = "a"
            else:
                winner = "tie"
            await self.storage.save_comparison({
                "run_a_id": run_a_id,
                "run_b_id": run_b_id,
                "suite_name": suite_name,
                "metric": target_type,
                "score_a": score_a,
                "score_b": score_b,
                "delta": delta,
                "winner": winner,
                "significant": significant,
            })
        
        return comparison

    async def detect_regression(self, suite_id: UUID, metric: str = "overall", last: int = 10) -> dict[str, Any]:
        runs = await self.storage.get_latest_runs(suite_id, limit=last)
        # Reverse to get chronological order
        runs.reverse()
        
        points: list[dict[str, Any]] = []
        for run in runs:
            # Placeholder: should use aggregate_scores if available
            score = 0.0
            if run.aggregate_scores and metric in run.aggregate_scores:
                score = float(run.aggregate_scores[metric])
            points.append({"date": str(run.created_at), "score": score})
            
        trend = "stable"
        if len(points) >= 2:
            first_score = float(points[0]["score"])
            last_score = float(points[-1]["score"])
            if last_score > first_score:
                trend = "improving"
            elif last_score < first_score:
                trend = "declining"

        return {
            "points": points,
            "trend": trend
        }
