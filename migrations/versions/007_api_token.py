"""Add API token fields on user

Revision ID: 007_api_token
Revises: 006_todos
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = '007_api_token'
down_revision = '006_todos'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('api_token_hash', sa.String(length=64), nullable=True))
    op.add_column('user', sa.Column('api_token_prefix', sa.String(length=12), nullable=True))
    op.create_index('ix_user_api_token_hash', 'user', ['api_token_hash'])


def downgrade():
    op.drop_index('ix_user_api_token_hash', table_name='user')
    op.drop_column('user', 'api_token_prefix')
    op.drop_column('user', 'api_token_hash')
