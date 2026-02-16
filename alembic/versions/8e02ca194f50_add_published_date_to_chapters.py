"""add_published_date_to_chapters

Revision ID: 8e02ca194f50
Revises: a1b2c3d4e5f6
Create Date: 2026-02-16 08:49:12.473292

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '8e02ca194f50'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('chapters')]
    if 'published_date' not in columns:
        op.add_column('chapters', sa.Column('published_date', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('chapters')]
    if 'published_date' in columns:
        op.drop_column('chapters', 'published_date')
