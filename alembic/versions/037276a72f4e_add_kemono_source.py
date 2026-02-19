"""add kemono source

Revision ID: 037276a72f4e
Revises: 20260221_add_notify
Create Date: 2026-02-18 17:44:55.145340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '037276a72f4e'
down_revision: Union[str, Sequence[str], None] = '20260221_add_notify'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if 'Kemono' already exists to be idempotent
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT count(*) FROM sources WHERE key = 'kemono'"))
    count = result.scalar()

    if count == 0:
        # is_enabled = 0 for False (disabled by default)
        op.execute("INSERT INTO sources (name, key, is_enabled) VALUES ('Kemono', 'kemono', 0)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM sources WHERE key = 'kemono'")
