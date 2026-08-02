from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.models import Account, Transaction, Loan, Investment
from app.security import require_owner, clamp_text, safe_float
from app.services.categories import list_categories, ensure_category
from app.services.investment_capital import refresh_total_invested
from app.services.email import (
    is_mail_configured,
    send_email,
    build_reminder_email,
    get_due_pending,
)

transactions_bp = Blueprint('transactions', __name__)


def _reverse_completed_effects(tx, user_id):
    if tx.status != 'completed':
        return
    account = Account.query.get(tx.account_id)
    if account:
        if tx.type == 'income':
            account.balance -= tx.amount
        else:
            account.balance += tx.amount
    if tx.loan_id:
        loan = Loan.query.get(tx.loan_id)
        if loan and loan.user_id == user_id and tx.type == 'expense':
            loan.outstanding = (loan.outstanding or 0) + tx.amount
            if loan.status == 'paid_off' and loan.outstanding > 0:
                loan.status = 'active'


def _apply_completed_effects(tx, user_id):
    if tx.status != 'completed':
        return
    account = Account.query.get(tx.account_id)
    if account:
        if tx.type == 'income':
            account.balance += tx.amount
        else:
            account.balance -= tx.amount
    if tx.loan_id:
        loan = Loan.query.get(tx.loan_id)
        if loan and loan.user_id == user_id and tx.type == 'expense':
            loan.outstanding = max(0.0, (loan.outstanding or 0) - tx.amount)
            if loan.outstanding <= 0:
                loan.outstanding = 0
                loan.status = 'paid_off'


@transactions_bp.route('/transactions')
@login_required
def transactions():
    status_filter = request.args.get('status', 'all')
    query = Transaction.query.filter_by(user_id=current_user.id)
    if status_filter == 'pending':
        query = query.filter_by(status='pending')
    elif status_filter == 'completed':
        query = query.filter_by(status='completed')
    return render_template(
        'transactions.html',
        transactions=query.order_by(Transaction.date.desc()).all(),
        status_filter=status_filter,
    )


@transactions_bp.route('/pending')
@login_required
def pending_payments():
    from datetime import date

    pending = (
        Transaction.query.filter_by(user_id=current_user.id, status='pending')
        .order_by(Transaction.due_date.asc().nullslast(), Transaction.date.desc())
        .all()
    )
    pending_total = sum(t.amount for t in pending if t.type == 'expense')
    return render_template(
        'pending.html',
        pending=pending,
        pending_total=pending_total,
        due_soon_count=len(get_due_pending(current_user.id)),
        mail_configured=is_mail_configured(),
        today=date.today(),
    )


@transactions_bp.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        account_id = int(request.form.get('account_id'))
        amount = safe_float(request.form.get('amount'), 0.0, min_v=0.01, max_v=1e12)
        if amount <= 0:
            flash('Amount must be positive.', 'danger')
            return redirect(url_for('transactions.add_transaction'))
        tx_type = request.form.get('type')
        description = clamp_text(request.form.get('description'), 200)
        category = ensure_category(
            current_user.id,
            clamp_text(request.form.get('category'), 50) or 'General',
        )
        status = request.form.get('status', 'completed')
        due_date_str = request.form.get('due_date')
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        account = require_owner(Account.query.get(account_id))

        if status == 'completed':
            if tx_type == 'income':
                account.balance += amount
            else:
                account.balance -= amount

        tx = Transaction(
            description=description,
            amount=amount,
            type=tx_type,
            status=status,
            category=category,
            due_date=due_date,
            account_id=account_id,
            user_id=current_user.id,
        )
        db.session.add(tx)
        db.session.commit()

        if status == 'pending':
            flash('Pending payment added.', 'info')
            return redirect(url_for('transactions.pending_payments'))
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('transactions.transactions'))
    categories = list_categories(current_user.id)
    return render_template(
        'add_transaction.html',
        accounts=accounts_list,
        categories=categories,
    )


@transactions_bp.route('/edit_transaction/<int:tx_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(tx_id):
    tx = require_owner(Transaction.query.get(tx_id))
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        old_inv_id = tx.investment_id
        _reverse_completed_effects(tx, current_user.id)

        account_id = int(request.form.get('account_id') or tx.account_id)
        amount = safe_float(request.form.get('amount'), tx.amount, min_v=0.01, max_v=1e12)
        if amount <= 0:
            flash('Amount must be positive.', 'danger')
            db.session.rollback()
            return redirect(url_for('transactions.edit_transaction', tx_id=tx.id))

        tx_type = request.form.get('type') or tx.type
        if tx_type not in ('income', 'expense'):
            tx_type = tx.type
        description = clamp_text(request.form.get('description'), 200) or tx.description
        category = ensure_category(
            current_user.id,
            clamp_text(request.form.get('category'), 50) or tx.category or 'General',
        )
        status = request.form.get('status') or tx.status
        if status not in ('pending', 'completed'):
            status = tx.status
        due_date_str = request.form.get('due_date')
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                due_date = tx.due_date
        elif status == 'pending':
            due_date = tx.due_date

        require_owner(Account.query.get(account_id))

        tx.description = description
        tx.amount = amount
        tx.type = tx_type
        tx.status = status
        tx.category = category
        tx.due_date = due_date
        tx.account_id = account_id

        _apply_completed_effects(tx, current_user.id)

        inv_ids = {i for i in (old_inv_id, tx.investment_id) if i}
        for iid in inv_ids:
            inv = Investment.query.get(iid)
            if inv and inv.user_id == current_user.id:
                refresh_total_invested(inv)

        db.session.commit()
        flash('Transaction updated.', 'success')
        if status == 'pending':
            return redirect(url_for('transactions.pending_payments'))
        return redirect(url_for('transactions.transactions'))

    categories = list_categories(current_user.id)
    return render_template(
        'edit_transaction.html',
        tx=tx,
        accounts=accounts_list,
        categories=categories,
    )


@transactions_bp.route('/mark_paid/<int:tx_id>', methods=['POST'])
@login_required
def mark_paid(tx_id):
    tx = require_owner(Transaction.query.get(tx_id))
    if tx.status != 'pending':
        flash('Already completed.', 'warning')
        return redirect(url_for('transactions.pending_payments'))

    account = Account.query.get(tx.account_id)
    if tx.type == 'income':
        account.balance += tx.amount
    else:
        account.balance -= tx.amount

    if tx.loan_id:
        loan = Loan.query.get(tx.loan_id)
        if loan and loan.user_id == current_user.id:
            loan.outstanding = max(0.0, loan.outstanding - tx.amount)
            if loan.outstanding <= 0:
                loan.outstanding = 0
                loan.status = 'paid_off'

    tx.status = 'completed'
    tx.date = datetime.utcnow()

    if tx.investment_id:
        inv = Investment.query.get(tx.investment_id)
        if inv and inv.user_id == current_user.id:
            refresh_total_invested(inv)

    db.session.commit()
    flash(f'"{tx.description}" marked as paid.', 'success')
    return redirect(url_for('transactions.pending_payments'))


@transactions_bp.route('/delete_transaction/<int:tx_id>', methods=['POST'])
@login_required
def delete_transaction(tx_id):
    tx = require_owner(Transaction.query.get(tx_id))
    inv_refresh = None
    if tx.investment_id:
        inv_refresh = Investment.query.get(tx.investment_id)

    if tx.status == 'completed':
        account = Account.query.get(tx.account_id)
        if tx.type == 'income':
            account.balance -= tx.amount
        else:
            account.balance += tx.amount
        if tx.loan_id:
            loan = Loan.query.get(tx.loan_id)
            if loan and loan.user_id == current_user.id:
                loan.outstanding += tx.amount
                if loan.status == 'paid_off' and loan.outstanding > 0:
                    loan.status = 'active'

    db.session.delete(tx)
    db.session.flush()
    if inv_refresh and inv_refresh.user_id == current_user.id:
        refresh_total_invested(inv_refresh)
    db.session.commit()
    flash('Transaction deleted.', 'success')
    return redirect(request.referrer or url_for('transactions.transactions'))


@transactions_bp.route('/send_reminder/<int:tx_id>', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def send_reminder(tx_id):
    tx = require_owner(Transaction.query.get(tx_id))
    if not current_user.email:
        flash('Set your email in Settings first.', 'warning')
        return redirect(url_for('settings.settings'))
    subject, html, text = build_reminder_email(current_user, [tx])
    ok, err = send_email(current_user.email, subject, html, text)
    if ok:
        tx.last_reminder_sent = datetime.utcnow()
        db.session.commit()
        flash(f'Reminder sent for "{tx.description}".', 'success')
    else:
        flash(f'Failed: {err}', 'danger')
    return redirect(url_for('transactions.pending_payments'))


@transactions_bp.route('/send_due_reminders', methods=['POST'])
@login_required
@limiter.limit('5 per hour')
def send_due_reminders():
    if not current_user.email:
        flash('Set your email in Settings first.', 'warning')
        return redirect(url_for('settings.settings'))
    due = get_due_pending(current_user.id)
    if not due:
        flash('No due/upcoming payments to remind.', 'info')
        return redirect(url_for('transactions.pending_payments'))
    subject, html, text = build_reminder_email(current_user, due)
    ok, err = send_email(current_user.email, subject, html, text)
    if ok:
        now = datetime.utcnow()
        for tx in due:
            tx.last_reminder_sent = now
        db.session.commit()
        flash(f'Reminders sent for {len(due)} payment(s).', 'success')
    else:
        flash(f'Failed: {err}', 'danger')
    return redirect(url_for('transactions.pending_payments'))
