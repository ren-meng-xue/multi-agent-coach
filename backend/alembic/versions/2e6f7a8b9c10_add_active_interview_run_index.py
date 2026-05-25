"""add active interview run index

Revision ID: 2e6f7a8b9c10
Revises: 9f1a2b3c4d5e
Create Date: 2026-05-25 00:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e6f7a8b9c10"
down_revision: str | Sequence[str] | None = "9f1a2b3c4d5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Ensure each user has at most one active interview run."""
    op.execute(
        """
        CREATE UNIQUE INDEX uq_interview_sessions_user_active
        ON interview_sessions (user_id)
        WHERE status = 'in_progress'
        """
    )


def downgrade() -> None:
    """Remove the active interview run uniqueness guard."""
    op.drop_index("uq_interview_sessions_user_active", table_name="interview_sessions")
