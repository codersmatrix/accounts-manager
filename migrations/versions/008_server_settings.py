"""Server settings table and user.is_admin

Revision ID: 008_server_settings
Revises: 007_api_token
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = '008_server_settings'
down_revision = '007_api_token'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'server_setting',
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )
    op.add_column('user', sa.Column('is_admin', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('user', 'is_admin')
    op.drop_table('server_setting')
