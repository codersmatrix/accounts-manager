"""Initial schema: users, accounts, transactions, loans, investments

Revision ID: 001_initial
Revises:
Create Date: 2026-07-29

"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('password_hash', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )

    op.create_table(
        'account',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('account_type', sa.String(length=50), nullable=True),
        sa.Column('balance', sa.Float(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'loan',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('lender_type', sa.String(length=30), nullable=True),
        sa.Column('payment_mode', sa.String(length=20), nullable=True),
        sa.Column('principal', sa.Float(), nullable=False),
        sa.Column('outstanding', sa.Float(), nullable=False),
        sa.Column('interest_rate', sa.Float(), nullable=True),
        sa.Column('emi_amount', sa.Float(), nullable=True),
        sa.Column('emi_day', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.String(length=300), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'investment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('inv_type', sa.String(length=30), nullable=True),
        sa.Column('monthly_sip', sa.Float(), nullable=True),
        sa.Column('sip_day', sa.Integer(), nullable=True),
        sa.Column('total_invested', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.String(length=300), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('type', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('date', sa.DateTime(), nullable=True),
        sa.Column('last_reminder_sent', sa.DateTime(), nullable=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('loan_id', sa.Integer(), nullable=True),
        sa.Column('investment_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['account.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['loan_id'], ['loan.id']),
        sa.ForeignKeyConstraint(['investment_id'], ['investment.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_transaction_user_status', 'transaction', ['user_id', 'status'])
    op.create_index('ix_transaction_due_date', 'transaction', ['due_date'])
    op.create_index('ix_loan_user_status', 'loan', ['user_id', 'status'])
    op.create_index('ix_investment_user_status', 'investment', ['user_id', 'status'])
    op.create_index('ix_account_user_id', 'account', ['user_id'])


def downgrade():
    op.drop_index('ix_account_user_id', table_name='account')
    op.drop_index('ix_investment_user_status', table_name='investment')
    op.drop_index('ix_loan_user_status', table_name='loan')
    op.drop_index('ix_transaction_due_date', table_name='transaction')
    op.drop_index('ix_transaction_user_status', table_name='transaction')
    op.drop_table('transaction')
    op.drop_table('investment')
    op.drop_table('loan')
    op.drop_table('account')
    op.drop_table('user')
