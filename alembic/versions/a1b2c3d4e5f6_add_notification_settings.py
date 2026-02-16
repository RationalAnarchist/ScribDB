"""Add notification settings

Revision ID: a1b2c3d4e5f6
Revises: 9a8b7c6d5e4f
Create Date: 2026-02-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c109d92524fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'notification_settings' not in tables:
        op.create_table('notification_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('kind', sa.String(), nullable=False),
            sa.Column('target', sa.String(), nullable=False),
            sa.Column('events', sa.String(), nullable=True, default=''),
            sa.Column('attach_file', sa.Boolean(), default=False),
            sa.Column('enabled', sa.Boolean(), default=True),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'notification_settings' in tables:
        op.drop_table('notification_settings')
