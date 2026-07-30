"""Add investment tags and investment_tag table

Revision ID: 004_investment_tags
Revises: 003_loan_tenure
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa

revision = '004_investment_tags'
down_revision = '003_loan_tenure'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('investment', sa.Column('tags', sa.String(length=300), nullable=True))
    op.create_table(
        'investment_tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_investment_tag_user_name'),
    )
    op.create_index('ix_investment_tag_user_id', 'investment_tag', ['user_id'])


def downgrade():
    op.drop_index('ix_investment_tag_user_id', table_name='investment_tag')
    op.drop_table('investment_tag')
    op.drop_column('investment', 'tags')
