"""add turn_trace_json to interview_messages

Revision ID: d834a422b1a2
Revises: e893374d74e3
Create Date: 2026-06-02 12:05:37.405132

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd834a422b1a2'
down_revision: Union[str, Sequence[str], None] = 'e893374d74e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "interview_messages",
        sa.Column("turn_trace_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("interview_messages", "turn_trace_json")
