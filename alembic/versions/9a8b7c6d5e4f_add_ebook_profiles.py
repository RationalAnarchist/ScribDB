"""Add ebook profiles

Revision ID: 9a8b7c6d5e4f
Revises: 801449fbce51
Create Date: 2026-02-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a8b7c6d5e4f'
down_revision: Union[str, Sequence[str], None] = '801449fbce51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'ebook_profiles' not in tables:
        op.create_table('ebook_profiles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('css', sa.String(), nullable=True),
            sa.Column('output_format', sa.String(), default='epub'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        # Insert default profile
        op.execute("INSERT INTO ebook_profiles (name, description, css, output_format) VALUES ('Standard', 'Default formatting', 'body { font-family: Times, Times New Roman, serif; }', 'epub')")

    columns = [c['name'] for c in inspector.get_columns('stories')]
    if 'profile_id' not in columns:
        with op.batch_alter_table('stories') as batch_op:
            batch_op.add_column(sa.Column('profile_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_stories_profile_id', 'ebook_profiles', ['profile_id'], ['id'])

        # Set default profile for existing stories
        op.execute("UPDATE stories SET profile_id = 1 WHERE profile_id IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'stories' in tables:
        columns = [c['name'] for c in inspector.get_columns('stories')]
        if 'profile_id' in columns:
            with op.batch_alter_table('stories') as batch_op:
                batch_op.drop_constraint('fk_stories_profile_id', type_='foreignkey')
                batch_op.drop_column('profile_id')

    if 'ebook_profiles' in tables:
        op.drop_table('ebook_profiles')
