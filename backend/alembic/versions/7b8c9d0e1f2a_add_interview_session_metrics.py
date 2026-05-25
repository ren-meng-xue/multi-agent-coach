"""add interview session metrics

Revision ID: 7b8c9d0e1f2a
Revises: 4a5b6c7d8e9f
Create Date: 2026-05-25 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b8c9d0e1f2a"
down_revision: str | Sequence[str] | None = "4a5b6c7d8e9f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist report-derived metrics directly on interview sessions."""
    op.add_column("interview_sessions", sa.Column("score", sa.Float(), nullable=True))
    op.add_column("interview_sessions", sa.Column("pass_fail", sa.String(length=20), nullable=True))
    op.add_column("interview_sessions", sa.Column("key_issues", sa.JSON(), nullable=True))
    op.create_check_constraint(
        "ck_interview_sessions_pass_fail",
        "interview_sessions",
        "pass_fail IS NULL OR pass_fail IN ('pass', 'fail', 'partial')",
    )


def downgrade() -> None:
    """Remove report-derived session metrics."""
    op.drop_constraint("ck_interview_sessions_pass_fail", "interview_sessions", type_="check")
    op.drop_column("interview_sessions", "key_issues")
    op.drop_column("interview_sessions", "pass_fail")
    op.drop_column("interview_sessions", "score")
