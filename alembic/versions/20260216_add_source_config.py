"""Add source config

Revision ID: 20260216_add_source_config
Revises: 0356439e54ae
Create Date: 2026-02-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260216_add_source_config'
down_revision: Union[str, Sequence[str], None] = '0356439e54ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'sources' not in tables:
        op.create_table('sources',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('key', sa.String(), nullable=False),
            sa.Column('is_enabled', sa.Boolean(), nullable=True),
            sa.Column('config', sa.String(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('key'),
            sa.UniqueConstraint('name')
        )
        # Insert default sources
        op.execute("INSERT INTO sources (name, key, is_enabled) VALUES ('Royal Road', 'royalroad', 1)")
        op.execute("INSERT INTO sources (name, key, is_enabled) VALUES ('Archive of Our Own', 'ao3', 1)")
    else:
        columns = [c['name'] for c in inspector.get_columns('sources')]
        if 'config' not in columns:
            op.add_column('sources', sa.Column('config', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('sources')]
    if 'config' in columns:
        op.drop_column('sources', 'config')
