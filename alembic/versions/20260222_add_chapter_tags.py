"""Add tags to chapters

Revision ID: 20260222_add_chapter_tags
Revises: 20260221_add_notify
Create Date: 2026-02-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '20260222_add_chapter_tags'
down_revision: Union[str, Sequence[str], None] = '037276a72f4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    columns_chapters = [c['name'] for c in inspector.get_columns('chapters')]
    if 'tags' not in columns_chapters:
        op.add_column('chapters', sa.Column('tags', sa.String(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    columns_chapters = [c['name'] for c in inspector.get_columns('chapters')]
    if 'tags' in columns_chapters:
        with op.batch_alter_table('chapters') as batch_op:
            batch_op.drop_column('tags')
