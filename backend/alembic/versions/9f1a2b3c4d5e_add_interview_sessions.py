"""add interview sessions

Revision ID: 9f1a2b3c4d5e
Revises: c7d4a8b2f091
Create Date: 2026-05-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f1a2b3c4d5e"
down_revision: str | Sequence[str] | None = "c7d4a8b2f091"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create interview session and message tables."""
    op.create_table(
        "interview_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="in_progress", nullable=False),
        sa.Column("target_role", sa.String(length=255), nullable=True),
        sa.Column("target_company", sa.String(length=255), nullable=True),
        sa.Column("user_background", sa.Text(), nullable=True),
        sa.Column("total_questions", sa.Integer(), server_default="5", nullable=False),
        sa.Column("question_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "question_count >= 0",
            name="ck_interview_sessions_question_count",
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_interview_sessions_status",
        ),
        sa.CheckConstraint(
            "total_questions > 0",
            name="ck_interview_sessions_total_questions",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interview_sessions_user_id"),
        "interview_sessions",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "interview_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=True),
        sa.Column("is_followup", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "question_number IS NULL OR question_number > 0",
            name="ck_interview_messages_question_number",
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="ck_interview_messages_role",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interview_messages_created_at"),
        "interview_messages",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interview_messages_session_id"),
        "interview_messages",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop interview session and message tables."""
    op.drop_index(op.f("ix_interview_messages_session_id"), table_name="interview_messages")
    op.drop_index(op.f("ix_interview_messages_created_at"), table_name="interview_messages")
    op.drop_table("interview_messages")
    op.drop_index(op.f("ix_interview_sessions_user_id"), table_name="interview_sessions")
    op.drop_table("interview_sessions")
