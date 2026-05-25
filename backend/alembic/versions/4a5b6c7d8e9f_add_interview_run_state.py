"""add interview run state

Revision ID: 4a5b6c7d8e9f
Revises: 2e6f7a8b9c10
Create Date: 2026-05-25 00:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a5b6c7d8e9f"
down_revision: str | Sequence[str] | None = "2e6f7a8b9c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist graph stage and per-question followup counter on interview runs."""
    op.add_column(
        "interview_sessions",
        sa.Column("stage", sa.String(length=20), server_default="opening", nullable=False),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("followup_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_interview_sessions_stage",
        "interview_sessions",
        "stage IN ('opening', 'interview', 'closing')",
    )
    op.create_check_constraint(
        "ck_interview_sessions_followup_count",
        "interview_sessions",
        "followup_count >= 0",
    )


def downgrade() -> None:
    """Remove persisted graph state fields."""
    op.drop_constraint(
        "ck_interview_sessions_followup_count",
        "interview_sessions",
        type_="check",
    )
    op.drop_constraint("ck_interview_sessions_stage", "interview_sessions", type_="check")
    op.drop_column("interview_sessions", "followup_count")
    op.drop_column("interview_sessions", "stage")
