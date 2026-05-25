"""add report_json to interview_sessions

Revision ID: 4cc2bf1fbaf8
Revises: 7b8c9d0e1f2a
Create Date: 2026-05-25 16:12:39.722427

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4cc2bf1fbaf8'
down_revision: Union[str, Sequence[str], None] = '7b8c9d0e1f2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("interview_sessions", sa.Column("report_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("interview_sessions", "report_json")
