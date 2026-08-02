"""Usage analytics events and user activity fields

Revision ID: 009_usage_analytics
Revises: 008_server_settings
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = '009_usage_analytics'
down_revision = '008_server_settings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'usage_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('path', sa.String(length=200), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=True),
        sa.Column('meta', sa.String(length=200), nullable=True),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_usage_event_event_type', 'usage_event', ['event_type'])
    op.create_index('ix_usage_event_user_id', 'usage_event', ['user_id'])
    op.create_index('ix_usage_event_created_at', 'usage_event', ['created_at'])

    op.add_column('user', sa.Column('is_active_flag', sa.Boolean(), nullable=True))
    op.add_column('user', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    op.add_column('user', sa.Column('created_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('user', 'created_at')
    op.drop_column('user', 'last_login_at')
    op.drop_column('user', 'is_active_flag')
    op.drop_index('ix_usage_event_created_at', table_name='usage_event')
    op.drop_index('ix_usage_event_user_id', table_name='usage_event')
    op.drop_index('ix_usage_event_event_type', table_name='usage_event')
    op.drop_table('usage_event')
