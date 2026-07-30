"""Add category table for user-defined transaction categories

Revision ID: 002_category
Revises: 001_initial
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa

revision = '002_category'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'category',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_category_user_name'),
    )
    op.create_index('ix_category_user_id', 'category', ['user_id'])


def downgrade():
    op.drop_index('ix_category_user_id', table_name='category')
    op.drop_table('category')
