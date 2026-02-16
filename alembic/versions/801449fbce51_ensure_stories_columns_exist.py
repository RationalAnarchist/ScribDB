"""Ensure stories columns exist

Revision ID: 801449fbce51
Revises: 20260216_add_source_config
Create Date: 2026-02-16 00:46:18.747400

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '801449fbce51'
down_revision: Union[str, Sequence[str], None] = '20260216_add_source_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('stories')]

    if 'description' not in columns:
        op.add_column('stories', sa.Column('description', sa.String(), nullable=True))
    if 'tags' not in columns:
        op.add_column('stories', sa.Column('tags', sa.String(), nullable=True))
    if 'rating' not in columns:
        op.add_column('stories', sa.Column('rating', sa.String(), nullable=True))
    if 'language' not in columns:
        op.add_column('stories', sa.Column('language', sa.String(), nullable=True))
    if 'publication_status' not in columns:
        op.add_column('stories', sa.Column('publication_status', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    pass
