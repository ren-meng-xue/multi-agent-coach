from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BOOLEAN,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class EvalSuite(Base):
    """评测套件（版本化）"""

    __tablename__ = "eval_suites"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    description: Mapped[str | None] = mapped_column(Text)
    judge_mode: Mapped[str] = mapped_column(String(20), nullable=False)  # rubric/comparative/binary
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    cases: Mapped[list["EvalCase"]] = relationship(
        back_populates="suite", cascade="all, delete-orphan"
    )
    runs: Mapped[list["EvalRun"]] = relationship(back_populates="suite")


class EvalCase(Base):
    """单个评测用例"""

    __tablename__ = "eval_cases"
    __table_args__ = (UniqueConstraint("suite_id", "case_key", name="uq_eval_cases_suite_case"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    suite_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("eval_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_key: Mapped[str] = mapped_column(String(100), nullable=False)  # 套件内唯一标识
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False, server_default="medium")
    tags: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    golden_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    suite: Mapped[EvalSuite] = relationship(back_populates="cases")


class EvalRun(Base):
    """一次评测执行"""

    __tablename__ = "eval_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_eval_runs_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    suite_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("eval_suites.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255))
    judge_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    judge_model: Mapped[str] = mapped_column(String(100), nullable=False)
    system_version: Mapped[str | None] = mapped_column(String(100))  # git SHA
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    total_cases: Mapped[int] = mapped_column(Integer, server_default="0")
    completed_cases: Mapped[int] = mapped_column(Integer, server_default="0")
    aggregate_scores: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    suite: Mapped[EvalSuite | None] = relationship(back_populates="runs")
    results: Mapped[list["EvalResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class EvalResult(Base):
    """单 case 评测结果"""

    __tablename__ = "eval_results"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("eval_cases.id", ondelete="SET NULL"),
    )
    case_key: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    system_output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    judge_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    judge_reasoning: Mapped[str | None] = mapped_column(Text)
    judge_model: Mapped[str | None] = mapped_column(String(100))
    binary_pass: Mapped[bool | None] = mapped_column(BOOLEAN)
    overall_score: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    run: Mapped[EvalRun] = relationship(back_populates="results")


class EvalComparison(Base):
    """A/B 对比结果"""

    __tablename__ = "eval_comparisons"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    run_a_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_b_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    suite_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)  # 对比的指标名
    score_a: Mapped[float] = mapped_column(Float, nullable=False)
    score_b: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)  # score_b - score_a
    winner: Mapped[str] = mapped_column(String(10), nullable=False)  # "a" / "b" / "tie"
    significant: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, server_default="false")
    report_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
