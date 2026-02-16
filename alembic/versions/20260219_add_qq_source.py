"""Add Questionable Questing source

Revision ID: 20260219_add_qq_source
Revises: 202602181200
Create Date: 2026-02-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260219_add_qq_source'
down_revision: Union[str, Sequence[str], None] = '202602181200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if 'Questionable Questing' already exists to be idempotent
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT count(*) FROM sources WHERE key = 'questionablequesting'"))
    count = result.scalar()

    if count == 0:
        op.execute("INSERT INTO sources (name, key, is_enabled) VALUES ('Questionable Questing', 'questionablequesting', 1)")


def downgrade() -> None:
    op.execute("DELETE FROM sources WHERE key = 'questionablequesting'")
