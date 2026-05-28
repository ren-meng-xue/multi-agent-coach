import pytest
from sqlalchemy import func, select

from app.models.eval import EvalCase, EvalComparison, EvalResult, EvalRun, EvalSuite


@pytest.mark.asyncio
async def test_create_eval_suite(db):
    suite = EvalSuite(
        name="interviewer_v0", 
        version=1, 
        judge_mode="rubric", 
        description="test"
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    assert suite.id is not None
    assert suite.name == "interviewer_v0"


@pytest.mark.asyncio
async def test_create_eval_case(db):
    suite = EvalSuite(name="test_case_suite", version=1, judge_mode="rubric")
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    
    case = EvalCase(
        suite_id=suite.id, 
        case_key="q_001", 
        target_type="question",
        input_json={"role": "AI"}, 
        difficulty="easy"
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    
    assert case.id is not None
    assert case.suite_id == suite.id
    assert case.case_key == "q_001"


@pytest.mark.asyncio
async def test_eval_run_lifecycle(db):
    suite = EvalSuite(name="test_run_suite", version=1, judge_mode="rubric")
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    
    run = EvalRun(
        suite_id=suite.id, 
        name="run_1", 
        judge_mode="rubric", 
        judge_model="gpt-4o"
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    
    assert run.status == "pending"
    
    run.status = "completed"
    run.completed_at = func.now()
    await db.commit()
    await db.refresh(run)
    
    assert run.status == "completed"
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_eval_result_cascade(db):
    # 验证 delete run 时 result 级联删除
    suite = EvalSuite(name="test_cascade_suite", version=1, judge_mode="rubric")
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    
    run = EvalRun(suite_id=suite.id, name="run_cascade", judge_mode="rubric", judge_model="gpt-4o")
    db.add(run)
    await db.commit()
    await db.refresh(run)
    
    result = EvalResult(
        run_id=run.id,
        case_key="q_001",
        target_type="question",
        system_output={"answer": "hello"}
    )
    db.add(result)
    await db.commit()
    
    # Check if result exists
    res = await db.execute(select(EvalResult).where(EvalResult.run_id == run.id))
    assert res.scalar_one_or_none() is not None
    
    # Delete run
    await db.delete(run)
    await db.commit()
    
    # Check if result is gone
    res = await db.execute(select(EvalResult).where(EvalResult.run_id == run.id))
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_eval_comparison(db):
    # 验证 comparison 创建和字段
    suite = EvalSuite(name="test_comp_suite", version=1, judge_mode="rubric")
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    
    run_a = EvalRun(suite_id=suite.id, name="run_a", judge_mode="rubric", judge_model="gpt-4o")
    run_b = EvalRun(suite_id=suite.id, name="run_b", judge_mode="rubric", judge_model="gpt-4o")
    db.add(run_a)
    db.add(run_b)
    await db.commit()
    await db.refresh(run_a)
    await db.refresh(run_b)
    
    comp = EvalComparison(
        run_a_id=run_a.id,
        run_b_id=run_b.id,
        suite_name="test_comp_suite",
        metric="overall_score",
        score_a=8.0,
        score_b=8.5,
        delta=0.5,
        winner="b",
        significant=True
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    
    assert comp.id is not None
    assert comp.delta == 0.5
    assert comp.winner == "b"
