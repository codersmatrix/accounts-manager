"""Add opening_amount for investment capital auto-calc

Revision ID: 005_investment_opening
Revises: 004_investment_tags
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa

revision = '005_investment_opening'
down_revision = '004_investment_tags'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('investment', sa.Column('opening_amount', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('investment', 'opening_amount')
