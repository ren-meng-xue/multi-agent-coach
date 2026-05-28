from typing import Any
from uuid import UUID

from app.eval.storage import EvalStorage


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
            if diff > 0.5:
                comparison["improved"].append(key)
            elif diff < -0.5:
                comparison["degraded"].append(key)
            else:
                comparison["stable"].append(key)
        
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
