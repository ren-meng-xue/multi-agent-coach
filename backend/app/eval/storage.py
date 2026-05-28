from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.eval import EvalCase, EvalComparison, EvalResult, EvalRun, EvalSuite


class EvalStorage:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_suite_by_name(self, name: str) -> EvalSuite | None:
        stmt = (
            select(EvalSuite)
            .options(selectinload(EvalSuite.cases))
            .where(EvalSuite.name == name)
            .order_by(EvalSuite.version.desc())
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_suites(self) -> list[EvalSuite]:
        stmt = select(EvalSuite).order_by(EvalSuite.name, EvalSuite.version.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def import_suite(self, suite_data: dict) -> EvalSuite:
        # Check if already exists
        stmt = select(EvalSuite).where(EvalSuite.name == suite_data["name"], EvalSuite.version == suite_data.get("version", 1))
        res = await self.db.execute(stmt)
        if res.scalars().first():
            # Already exists, just return it or update? For now just return
            s = await self.get_suite_by_name(suite_data["name"])
            if not s:
                raise ValueError("Suite disappeared while importing")
            return s

        suite = EvalSuite(
            name=suite_data["name"],
            version=suite_data.get("version", 1),
            description=suite_data.get("description"),
            judge_mode=suite_data["judge_mode"],
            case_count=len(suite_data["cases"]),
        )
        self.db.add(suite)
        await self.db.flush()

        for case_data in suite_data["cases"]:
            case = EvalCase(
                suite_id=suite.id,
                case_key=case_data["id"],
                target_type=case_data["target_type"],
                difficulty=case_data.get("difficulty", "medium"),
                tags=case_data.get("tags", []),
                input_json=case_data["input_json"],
                golden_json=case_data.get("golden"),
            )
            self.db.add(case)
        
        await self.db.commit()
        await self.db.refresh(suite)
        return suite

    async def create_run(self, suite_id: UUID | None, name: str, judge_mode: str, judge_model: str, total_cases: int, system_version: str | None = None) -> EvalRun:
        run = EvalRun(
            suite_id=suite_id,
            name=name,
            judge_mode=judge_mode,
            judge_model=judge_model,
            total_cases=total_cases,
            system_version=system_version,
            status="pending",
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def update_run(self, run_id: UUID, **kwargs):
        run = await self.db.get(EvalRun, run_id)
        if run:
            for k, v in kwargs.items():
                setattr(run, k, v)
            await self.db.commit()

    async def increment_completed_cases(self, run_id: UUID) -> None:
        await self.db.execute(
            text(
                "UPDATE eval_runs SET completed_cases = completed_cases + 1 "
                "WHERE id = :run_id"
            ),
            {"run_id": run_id},
        )
        await self.db.commit()

    async def save_result(self, result_data: dict) -> EvalResult:
        result = EvalResult(**result_data)
        self.db.add(result)
        await self.db.commit()
        return result

    async def get_run(self, run_id: UUID) -> EvalRun | None:
        stmt = select(EvalRun).options(selectinload(EvalRun.suite)).where(EvalRun.id == run_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_results(self, run_id: UUID) -> list[EvalResult]:
        stmt = select(EvalResult).where(EvalResult.run_id == run_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_comparison(self, comparison_data: dict) -> EvalComparison:
        comparison = EvalComparison(**comparison_data)
        self.db.add(comparison)
        await self.db.commit()
        return comparison
    
    async def get_latest_runs(self, suite_id: UUID, limit: int = 10) -> list[EvalRun]:
        stmt = select(EvalRun).where(EvalRun.suite_id == suite_id).order_by(EvalRun.created_at.desc()).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
