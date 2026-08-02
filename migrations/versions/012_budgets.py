"""Monthly budgets

Revision ID: 012_budgets
Revises: 011_password_reset
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = '012_budgets'
down_revision = '011_password_reset'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'budget',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('notes', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'category', 'year', 'month', name='uq_budget_user_cat_period'),
    )
    op.create_index('ix_budget_user_id', 'budget', ['user_id'])


def downgrade():
    op.drop_index('ix_budget_user_id', table_name='budget')
    op.drop_table('budget')
