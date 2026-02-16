"""Add volume_title and provider_name

Revision ID: 20260220_add_vol_provider
Revises: 20260219_add_qq_source
Create Date: 2026-02-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '20260220_add_vol_provider'
down_revision: Union[str, Sequence[str], None] = '20260219_add_qq_source'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Add volume_title to chapters
    columns_chapters = [c['name'] for c in inspector.get_columns('chapters')]
    if 'volume_title' not in columns_chapters:
        op.add_column('chapters', sa.Column('volume_title', sa.String(), nullable=True))

    # Add provider_name to stories
    columns_stories = [c['name'] for c in inspector.get_columns('stories')]
    if 'provider_name' not in columns_stories:
        op.add_column('stories', sa.Column('provider_name', sa.String(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Remove volume_title from chapters
    columns_chapters = [c['name'] for c in inspector.get_columns('chapters')]
    if 'volume_title' in columns_chapters:
        with op.batch_alter_table('chapters') as batch_op:
            batch_op.drop_column('volume_title')

    # Remove provider_name from stories
    columns_stories = [c['name'] for c in inspector.get_columns('stories')]
    if 'provider_name' in columns_stories:
        with op.batch_alter_table('stories') as batch_op:
            batch_op.drop_column('provider_name')
