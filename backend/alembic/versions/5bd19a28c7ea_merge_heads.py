"""merge_heads

Revision ID: 5bd19a28c7ea
Revises: ca72dbc9da5b, d7e8f9a0b1c2
Create Date: 2026-06-02 10:51:57.116866

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bd19a28c7ea'
down_revision: Union[str, Sequence[str], None] = ('ca72dbc9da5b', 'd7e8f9a0b1c2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
