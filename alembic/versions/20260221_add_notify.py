"""Add notify_on_new_chapter to stories

Revision ID: 20260221_add_notify
Revises: 20260220_add_qq_all
Create Date: 2026-02-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '20260221_add_notify'
down_revision: Union[str, Sequence[str], None] = '20260220_add_qq_all'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    columns_stories = [c['name'] for c in inspector.get_columns('stories')]
    if 'notify_on_new_chapter' not in columns_stories:
        # Use server_default='1' for SQLite/boolean true
        op.add_column('stories', sa.Column('notify_on_new_chapter', sa.Boolean(), server_default='1', default=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    columns_stories = [c['name'] for c in inspector.get_columns('stories')]
    if 'notify_on_new_chapter' in columns_stories:
        with op.batch_alter_table('stories') as batch_op:
            batch_op.drop_column('notify_on_new_chapter')
