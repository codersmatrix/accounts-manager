from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Account, Transaction, Loan, Investment
from app.services.email import (
    is_mail_configured,
    send_email,
    build_reminder_email,
    get_due_pending,
)

transactions_bp = Blueprint('transactions', __name__)


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
        amount = float(request.form.get('amount'))
        tx_type = request.form.get('type')
        description = request.form.get('description').strip()
        category = request.form.get('category') or 'General'
        status = request.form.get('status', 'completed')
        due_date_str = request.form.get('due_date')
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        account = Account.query.get_or_404(account_id)
        if account.user_id != current_user.id:
            flash('Unauthorized', 'danger')
            return redirect(url_for('dashboard.dashboard'))

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
    return render_template('add_transaction.html', accounts=accounts_list)


@transactions_bp.route('/mark_paid/<int:tx_id>', methods=['POST'])
@login_required
def mark_paid(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if tx.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard.dashboard'))
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

    if tx.investment_id:
        inv = Investment.query.get(tx.investment_id)
        if inv and inv.user_id == current_user.id:
            inv.total_invested = (inv.total_invested or 0) + tx.amount

    tx.status = 'completed'
    tx.date = datetime.utcnow()
    db.session.commit()
    flash(f'"{tx.description}" marked as paid.', 'success')
    return redirect(url_for('transactions.pending_payments'))


@transactions_bp.route('/delete_transaction/<int:tx_id>', methods=['POST'])
@login_required
def delete_transaction(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if tx.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard.dashboard'))

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
        if tx.investment_id:
            inv = Investment.query.get(tx.investment_id)
            if inv and inv.user_id == current_user.id:
                inv.total_invested = max(0.0, (inv.total_invested or 0) - tx.amount)

    db.session.delete(tx)
    db.session.commit()
    flash('Transaction deleted.', 'success')
    return redirect(request.referrer or url_for('transactions.transactions'))


@transactions_bp.route('/send_reminder/<int:tx_id>', methods=['POST'])
@login_required
def send_reminder(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if tx.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('transactions.pending_payments'))
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
