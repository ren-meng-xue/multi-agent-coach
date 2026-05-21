"""enable pgvector extension

Revision ID: c7d4a8b2f091
Revises: b9531ef59bd5
Create Date: 2026-05-22 00:55:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d4a8b2f091"
down_revision: str | Sequence[str] | None = "b9531ef59bd5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable pgvector before creating any vector-backed memory tables."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Remove pgvector when rolling back the extension migration."""
    op.execute("DROP EXTENSION IF EXISTS vector")
