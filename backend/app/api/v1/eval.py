from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.eval.dimensions import JudgeMode
from app.eval.judge import BaseJudge, BinaryJudge, ComparativeJudge, RubricJudge
from app.eval.regression import RegressionTester
from app.eval.runner import EvalRunner
from app.eval.schemas import JudgeConfig
from app.eval.storage import EvalStorage
from app.eval.system_calls import dispatch_system_call
from app.schemas.eval import (
    CompareRequest,
    EvalRunResponse,
    EvalRunSummary,
    EvalSuiteResponse,
    TrendResponse,
    TriggerEvalRequest,
)

router = APIRouter(prefix="/eval")


async def get_db():
    async with async_session_factory() as db:
        yield db


def verify_eval_auth(run_llm_eval: Annotated[str | None, Header()] = None):
    settings = get_settings()
    secret = (
        settings.run_llm_eval_secret.get_secret_value()
        if settings.run_llm_eval_secret
        else None
    )
    if secret and run_llm_eval == secret:
        return
    if settings.app_env == "dev":
        return
    raise HTTPException(status_code=403, detail="Not authorized to run evaluation")


@router.post("/runs", response_model=UUID, dependencies=[Depends(verify_eval_auth)])
async def trigger_eval(
    request: TriggerEvalRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    storage = EvalStorage(db)
    suite = await storage.get_suite_by_name(request.suite)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")

    cases = list(suite.cases)
    if request.limit:
        cases = cases[:request.limit]

    judge_config = JudgeConfig(
        model=request.judge_model or "gpt-4o",
        mode=request.judge_mode,
    )
    judge: BaseJudge
    if request.judge_mode == JudgeMode.RUBRIC:
        judge = RubricJudge(judge_config)
    elif request.judge_mode == JudgeMode.COMPARATIVE:
        judge = ComparativeJudge(judge_config)
    else:
        judge = BinaryJudge(judge_config)

    run = await storage.create_run(
        suite_id=suite.id,
        name=f"API Run {request.suite}",
        judge_mode=request.judge_mode.value,
        judge_model=judge_config.model,
        total_cases=len(cases),
        system_version=request.system_version
    )
    run_id = run.id

    # background task 会在请求 session 关闭后才运行，必须把 cases 从
    # 请求 session 解绑，否则 runner 内部并发 task 仍会撞共享 session race。
    for c in cases:
        db.expunge(c)

    settings = get_settings()
    runner = EvalRunner(
        async_session_factory, judge, dispatch_system_call,
        max_concurrency=settings.eval_max_concurrency,
    )

    async def _safe_run():
        try:
            await runner.run(run_id, cases)
        except Exception:
            import structlog
            _log = structlog.get_logger("app.eval.api")
            _log.error("eval_run_crashed", run_id=str(run_id))
            async with async_session_factory() as fail_db:
                fail_storage = EvalStorage(fail_db)
                await fail_storage.update_run(run_id, status="failed")

    background_tasks.add_task(_safe_run)

    return run_id


@router.get("/runs", response_model=list[EvalRunResponse], dependencies=[Depends(verify_eval_auth)])
async def list_runs(
    suite_name: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    # This needs a better implementation in storage to filter by name/status
    # For now, just list all
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.eval import EvalRun, EvalSuite
    stmt = select(EvalRun).options(selectinload(EvalRun.suite))
    if suite_name:
        stmt = stmt.join(EvalSuite).where(EvalSuite.name == suite_name)
    if status:
        stmt = stmt.where(EvalRun.status == status)
    stmt = stmt.order_by(EvalRun.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    runs = res.scalars().all()
    
    # Map suite name
    results = []
    for r in runs:
        resp = EvalRunResponse.model_validate(r)
        resp.suite_name = r.suite.name if r.suite else None
        results.append(resp)
    return results


@router.get("/runs/{run_id}", response_model=EvalRunSummary, dependencies=[Depends(verify_eval_auth)])
async def get_run_detail(run_id: UUID, db: AsyncSession = Depends(get_db)):
    storage = EvalStorage(db)
    run = await storage.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    results = await storage.get_results(run_id)
    
    # Group by type
    stats = {}
    for r in results:
        t = r.target_type
        if t not in stats:
            stats[t] = {"sum": 0.0, "pass": 0, "count": 0}
        stats[t]["sum"] += (r.overall_score or 0.0)
        if r.binary_pass:
            stats[t]["pass"] += 1
        stats[t]["count"] += 1
    
    results_by_type = {
        t: {
            "avg": v["sum"] / v["count"] if v["count"] > 0 else 0,
            "pass_rate": v["pass"] / v["count"] if v["count"] > 0 else 0,
            "count": v["count"]
        }
        for t, v in stats.items()
    }

    resp = EvalRunSummary.model_validate(run)
    resp.suite_name = run.suite.name if run.suite else None
    resp.results_by_type = results_by_type
    return resp


@router.post("/compare", dependencies=[Depends(verify_eval_auth)])
async def compare_runs(request: CompareRequest, db: AsyncSession = Depends(get_db)):
    storage = EvalStorage(db)
    tester = RegressionTester(storage)
    return await tester.compare_runs(request.run_a_id, request.run_b_id)


@router.get("/trend", response_model=TrendResponse, dependencies=[Depends(verify_eval_auth)])
async def get_trend(
    suite_name: str,
    metric: str = "overall",
    last: int = 10,
    db: AsyncSession = Depends(get_db)
):
    storage = EvalStorage(db)
    suite = await storage.get_suite_by_name(suite_name)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    
    tester = RegressionTester(storage)
    res = await tester.detect_regression(suite.id, metric=metric, last=last)
    return {
        "suite_name": suite_name,
        "metric": metric,
        "points": res["points"],
        "degraded": res["trend"] == "declining",
        "trend": res["trend"]
    }


@router.get("/suites", response_model=list[EvalSuiteResponse], dependencies=[Depends(verify_eval_auth)])
async def list_suites_api(db: AsyncSession = Depends(get_db)):
    storage = EvalStorage(db)
    return await storage.list_suites()
