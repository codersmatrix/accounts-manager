"""Add balance tenure fields to loan

Revision ID: 003_loan_tenure
Revises: 002_category
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa

revision = '003_loan_tenure'
down_revision = '002_category'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('loan', sa.Column('tenure_value', sa.Integer(), nullable=True))
    op.add_column('loan', sa.Column('tenure_unit', sa.String(length=10), nullable=True))


def downgrade():
    op.drop_column('loan', 'tenure_unit')
    op.drop_column('loan', 'tenure_value')
