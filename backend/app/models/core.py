"""核心业务模型：用户、面试 Session 与面试消息。"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    """用户表：Clerk user_id 为主键（VARCHAR，如 user_2abcDEF...）。"""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    target_role: Mapped[str | None] = mapped_column(String(255))
    work_years: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    stories: Mapped[list["UserStory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserStory(Base):
    """用户的 STAR 故事库，用于面试时提取项目细节。"""

    __tablename__ = "user_stories"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="stories")


class InterviewSession(Base):
    """一场模拟面试的总记录，用于恢复进度、区分新老用户和后续分析。"""

    __tablename__ = "interview_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_interview_sessions_status",
        ),
        CheckConstraint(
            "stage IN ('opening', 'interview', 'closing')",
            name="ck_interview_sessions_stage",
        ),
        CheckConstraint(
            "pass_fail IS NULL OR pass_fail IN ('pass', 'fail', 'partial')",
            name="ck_interview_sessions_pass_fail",
        ),
        CheckConstraint("total_questions > 0", name="ck_interview_sessions_total_questions"),
        CheckConstraint("question_count >= 0", name="ck_interview_sessions_question_count"),
        CheckConstraint("followup_count >= 0", name="ck_interview_sessions_followup_count"),
        Index(
            "uq_interview_sessions_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="in_progress")
    stage: Mapped[str] = mapped_column(String(20), nullable=False, server_default="opening")
    target_role: Mapped[str | None] = mapped_column(String(255))
    target_company: Mapped[str | None] = mapped_column(String(255))
    user_background: Mapped[str | None] = mapped_column(Text)
    total_questions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="5",
    )
    question_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    followup_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(Float)
    pass_fail: Mapped[str | None] = mapped_column(String(20))
    key_issues: Mapped[list[str] | None] = mapped_column(JSON)
    report_json: Mapped[dict | None] = mapped_column(JSON)
    use_qa_bank: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    user: Mapped[User] = relationship(back_populates="interview_sessions")
    messages: Mapped[list["InterviewMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewMessage.created_at",
    )
    coach_plan: Mapped["CoachPlan | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )


class InterviewMessage(Base):
    """面试中的单条消息，保存完整上下文供 LangGraph 和后续 Agent 使用。"""

    __tablename__ = "interview_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_interview_messages_role"),
        CheckConstraint(
            "question_number IS NULL OR question_number > 0",
            name="ck_interview_messages_question_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    question_number: Mapped[int | None] = mapped_column(Integer)
    is_followup: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    session: Mapped[InterviewSession] = relationship(back_populates="messages")


class CandidateMemory(Base):
    """跨 session 的候选人画像汇总，user_id 维度聚合。"""

    __tablename__ = "candidate_memory"

    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    latest_level: Mapped[str | None] = mapped_column(String(20))
    cumulative_signals: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    weakness_tags: Mapped[list[dict]] = mapped_column(JSONB, server_default="[]")
    last_session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="SET NULL"),
    )
    total_sessions: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship()
    last_session: Mapped["InterviewSession | None"] = relationship()


class CoachPlan(Base):
    """每次 coach 复盘产出的训练计划。"""

    __tablename__ = "coach_plans"
    __table_args__ = (
        Index(
            "idx_coach_plans_user_unconsumed",
            "user_id",
            postgresql_where=text("consumed = false"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="SET NULL"),
    )
    plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship()
    session: Mapped["InterviewSession | None"] = relationship(back_populates="coach_plan")
