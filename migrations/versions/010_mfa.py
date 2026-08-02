"""Add MFA fields to user

Revision ID: 010_mfa
Revises: 009_usage_analytics
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = '010_mfa'
down_revision = '009_usage_analytics'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('mfa_secret', sa.String(length=32), nullable=True))
    op.add_column('user', sa.Column('mfa_enabled', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('user', 'mfa_enabled')
    op.drop_column('user', 'mfa_secret')
