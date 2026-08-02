"""Password reset token fields

Revision ID: 011_password_reset
Revises: 010_mfa
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = '011_password_reset'
down_revision = '010_mfa'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('reset_token_hash', sa.String(length=64), nullable=True))
    op.add_column('user', sa.Column('reset_token_expires', sa.DateTime(), nullable=True))
    op.create_index('ix_user_reset_token_hash', 'user', ['reset_token_hash'])


def downgrade():
    op.drop_index('ix_user_reset_token_hash', table_name='user')
    op.drop_column('user', 'reset_token_expires')
    op.drop_column('user', 'reset_token_hash')
