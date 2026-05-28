from app.models.eval import EvalRun


class EvalReporter:
    def generate_markdown(self, run: EvalRun, results: list) -> str:
        md = f"# Eval Run Report: {run.name or run.id}\n\n"
        md += f"- **Suite**: {run.suite.name if run.suite else 'Unknown'}\n"
        md += f"- **Status**: {run.status}\n"
        md += f"- **Judge**: {run.judge_model} ({run.judge_mode})\n"
        md += f"- **Progress**: {run.completed_cases}/{run.total_cases}\n\n"
        
        md += "## Results\n\n"
        md += "| Case Key | Type | Score | Pass | Latency |\n"
        md += "| --- | --- | --- | --- | --- |\n"
        for r in results:
            md += f"| {r.case_key} | {r.target_type} | {r.overall_score} | {r.binary_pass} | {r.latency_ms}ms |\n"
            
        return md

    def generate_json(self, run: EvalRun, results: list) -> dict:
        return {
            "run": {
                "id": str(run.id),
                "name": run.name,
                "status": run.status,
                "total_cases": run.total_cases,
                "completed_cases": run.completed_cases,
            },
            "results": [
                {
                    "case_key": r.case_key,
                    "target_type": r.target_type,
                    "overall_score": r.overall_score,
                    "binary_pass": r.binary_pass,
                    "latency_ms": r.latency_ms,
                }
                for r in results
            ]
        }
