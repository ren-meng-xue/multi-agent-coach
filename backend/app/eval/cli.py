import argparse
import asyncio
import json
from uuid import UUID

from app.db.session import async_session_factory
from app.eval.datasets import load_suite
from app.eval.dimensions import JudgeMode
from app.eval.judge import BinaryJudge, ComparativeJudge, RubricJudge
from app.eval.regression import RegressionTester
from app.eval.reporter import EvalReporter
from app.eval.runner import EvalRunner
from app.eval.schemas import JudgeConfig
from app.eval.storage import EvalStorage


async def run_eval(args):
    async with async_session_factory() as db:
        storage = EvalStorage(db)
        suite = await storage.get_suite_by_name(args.suite)
        if not suite:
            print(f"Suite {args.suite} not found in DB.")
            return

        # Mock system call for now (actual logic would involve calling the Agent)
        async def mock_system_call(input_json):
            await asyncio.sleep(0.1)
            return {"answer": "mock answer"}

        judge_config = JudgeConfig(model=args.judge_model, mode=args.judge_mode)
        if args.judge_mode == JudgeMode.RUBRIC:
            judge = RubricJudge(judge_config)
        elif args.judge_mode == JudgeMode.COMPARATIVE:
            judge = ComparativeJudge(judge_config)
        else:
            judge = BinaryJudge(judge_config)

        runner = EvalRunner(storage, judge, mock_system_call)
        
        cases = suite.cases
        if args.limit:
            cases = cases[:args.limit]
            
        print(f"Running {len(cases)} cases for suite {args.suite}...")
        run = await storage.create_run(
            suite_id=suite.id,
            name=f"CLI Run {args.suite}",
            judge_mode=args.judge_mode,
            judge_model=args.judge_model,
            total_cases=len(cases),
            system_version=args.system_version
        )
        
        if not args.dry_run:
            await runner.run(run.id, cases)
            print(f"Run {run.id} completed.")
        else:
            print(f"Dry run: created run {run.id}")


async def import_suite_cmd(args):
    data = load_suite(args.file)
    async with async_session_factory() as db:
        storage = EvalStorage(db)
        suite = await storage.import_suite(data)
        print(f"Imported suite {suite.name} (v{suite.version}) with {suite.case_count} cases.")


async def list_suites_cmd(args):
    async with async_session_factory() as db:
        storage = EvalStorage(db)
        suites = await storage.list_suites()
        for s in suites:
            print(f"- {s.name} (v{s.version}): {s.case_count} cases, mode={s.judge_mode}")


async def compare_runs(args):
    async with async_session_factory() as db:
        storage = EvalStorage(db)
        tester = RegressionTester(storage)
        res = await tester.compare_runs(UUID(args.baseline), UUID(args.experiment))
        print(json.dumps(res, indent=2))


async def trend_cmd(args):
    async with async_session_factory() as db:
        storage = EvalStorage(db)
        suite = await storage.get_suite_by_name(args.suite)
        if not suite:
            print("Suite not found.")
            return
        tester = RegressionTester(storage)
        res = await tester.detect_regression(suite.id, metric=args.metric, last=args.last)
        print(json.dumps(res, indent=2))


async def report_cmd(args):
    async with async_session_factory() as db:
        storage = EvalStorage(db)
        run = await storage.get_run(UUID(args.run_id))
        if not run:
            print("Run not found.")
            return
        results = await storage.get_results(run.id)
        reporter = EvalReporter()
        if args.format == "markdown":
            print(reporter.generate_markdown(run, results))
        else:
            print(json.dumps(reporter.generate_json(run, results), indent=2))


def main():
    parser = argparse.ArgumentParser(description="Eval CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Run
    run_p = subparsers.add_parser("run")
    run_p.add_argument("--suite", required=True)
    run_p.add_argument("--judge-model", default="gpt-4o")
    run_p.add_argument("--judge-mode", default="rubric")
    run_p.add_argument("--limit", type=int)
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--system-version", default="HEAD")

    # Import
    import_p = subparsers.add_parser("import-suite")
    import_p.add_argument("--file", required=True)

    # List
    subparsers.add_parser("list-suites")

    # Compare
    comp_p = subparsers.add_parser("compare")
    comp_p.add_argument("--suite", required=True)
    comp_p.add_argument("--baseline", required=True)
    comp_p.add_argument("--experiment", required=True)
    comp_p.add_argument("--metric", default="overall")

    # Trend
    trend_p = subparsers.add_parser("trend")
    trend_p.add_argument("--suite", required=True)
    trend_p.add_argument("--metric", default="overall")
    trend_p.add_argument("--last", type=int, default=10)

    # Report
    report_p = subparsers.add_parser("report")
    report_p.add_argument("--run-id", required=True)
    report_p.add_argument("--format", choices=["markdown", "json"], default="markdown")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(run_eval(args))
    elif args.command == "import-suite":
        asyncio.run(import_suite_cmd(args))
    elif args.command == "list-suites":
        asyncio.run(list_suites_cmd(args))
    elif args.command == "compare":
        asyncio.run(compare_runs(args))
    elif args.command == "trend":
        asyncio.run(trend_cmd(args))
    elif args.command == "report":
        asyncio.run(report_cmd(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
