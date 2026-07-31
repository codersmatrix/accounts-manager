"""Add todo / reminder table

Revision ID: 006_todos
Revises: 005_investment_opening
Create Date: 2026-07-31

"""
from alembic import op
import sqlalchemy as sa

revision = '006_todos'
down_revision = '005_investment_opening'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'todo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('cadence', sa.String(length=20), nullable=True),
        sa.Column('cadence_day', sa.Integer(), nullable=True),
        sa.Column('next_due', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('last_reminded_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_todo_user_status', 'todo', ['user_id', 'status'])
    op.create_index('ix_todo_next_due', 'todo', ['next_due'])


def downgrade():
    op.drop_index('ix_todo_next_due', table_name='todo')
    op.drop_index('ix_todo_user_status', table_name='todo')
    op.drop_table('todo')
