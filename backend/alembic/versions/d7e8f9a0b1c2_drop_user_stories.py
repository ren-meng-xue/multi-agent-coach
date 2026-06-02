"""drop user_stories table

Revision ID: d7e8f9a0b1c2
Revises: cbe658f34eb2
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'cbe658f34eb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_user_stories_user_id'), table_name='user_stories')
    op.drop_table('user_stories')


def downgrade() -> None:
    op.create_table('user_stories',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=255), nullable=True),
    sa.Column('tags', sa.JSON(), nullable=True),
    sa.Column('content_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_stories_user_id'), 'user_stories', ['user_id'], unique=False)
