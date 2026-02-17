"""Add Questionable Questing (All Posts) source record

Revision ID: 20260220_add_qq_all
Revises: 20260220_add_vol_provider
Create Date: 2026-02-20 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260220_add_qq_all'
down_revision: Union[str, Sequence[str], None] = '20260220_add_vol_provider'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if 'Questionable Questing (All Posts)' already exists
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT count(*) FROM sources WHERE key = 'questionablequesting_all'"))
    count = result.scalar()

    if count == 0:
        op.execute("INSERT INTO sources (name, key, is_enabled) VALUES ('Questionable Questing (All Posts)', 'questionablequesting_all', 1)")


def downgrade() -> None:
    op.execute("DELETE FROM sources WHERE key = 'questionablequesting_all'")
