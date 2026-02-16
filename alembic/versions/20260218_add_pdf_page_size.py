"""add_pdf_page_size

Revision ID: 202602181200
Revises: 8e02ca194f50
Create Date: 2026-02-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '202602181200'
down_revision: Union[str, Sequence[str], None] = '8e02ca194f50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('ebook_profiles')]
    if 'pdf_page_size' not in columns:
        op.add_column('ebook_profiles', sa.Column('pdf_page_size', sa.String(), nullable=True, server_default='A4'))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('ebook_profiles')]
    if 'pdf_page_size' in columns:
        op.drop_column('ebook_profiles', 'pdf_page_size')
