from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.security import require_owner, clamp_text, safe_float, safe_int
from app.services.categories import ensure_category
from app.models import Account, Transaction, Loan

loans_bp = Blueprint('loans', __name__)

def _parse_tenure(form):
    """Return (tenure_value, tenure_unit) from form data."""
    raw = form.get('tenure_value', '').strip()
    if raw in (None, ''):
        return None, 'months'
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return None, 'months'
    if value < 0:
        value = 0
    if value > 600:  # 50 years max
        value = 600
    unit = form.get('tenure_unit', 'months')
    if unit not in ('months', 'years'):
        unit = 'months'
    return value, unit


@loans_bp.route('/loans')
@login_required
def loans():
    active = Loan.query.filter_by(user_id=current_user.id, status='active').order_by(Loan.name).all()
    paid = Loan.query.filter_by(user_id=current_user.id, status='paid_off').order_by(Loan.name).all()
    return render_template(
        'loans.html',
        active_loans=active,
        paid_loans=paid,
        total_debt=sum(l.outstanding for l in active),
        monthly_emi=sum(
            l.emi_amount for l in active
            if l.emi_amount and (l.payment_mode or 'emi') == 'emi'
        ),
        today=date.today(),
    )


@loans_bp.route('/add_loan', methods=['GET', 'POST'])
@login_required
def add_loan():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        principal = float(request.form.get('principal') or 0)
        outstanding_raw = request.form.get('outstanding')
        outstanding = float(outstanding_raw) if outstanding_raw not in (None, '') else principal
        if not name or principal <= 0:
            flash('Name and positive principal required.', 'danger')
            return redirect(url_for('loans.add_loan'))
        emi_day = max(1, min(28, int(request.form.get('emi_day') or 1)))
        start_date = None
        start_str = request.form.get('start_date')
        if start_str:
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        payment_mode = request.form.get('payment_mode', 'emi')
        if payment_mode not in ('emi', 'one_time'):
            payment_mode = 'emi'
        emi_amount = 0.0 if payment_mode == 'one_time' else float(request.form.get('emi_amount') or 0)
        tenure_value, tenure_unit = _parse_tenure(request.form)
        loan = Loan(
            name=name,
            lender_type=request.form.get('lender_type', 'bank'),
            payment_mode=payment_mode,
            principal=principal,
            outstanding=outstanding,
            interest_rate=float(request.form.get('interest_rate') or 0),
            emi_amount=emi_amount,
            emi_day=emi_day,
            tenure_value=tenure_value,
            tenure_unit=tenure_unit,
            start_date=start_date,
            notes=request.form.get('notes', '').strip(),
            status='active',
            user_id=current_user.id,
        )
        db.session.add(loan)
        db.session.commit()
        flash(f'Loan "{name}" added.', 'success')
        return redirect(url_for('loans.loans'))
    return render_template('add_loan.html')


@loans_bp.route('/loan/<int:loan_id>')
@login_required
def loan_detail(loan_id):
    loan = require_owner(Loan.query.get(loan_id))
    payments = Transaction.query.filter_by(loan_id=loan.id).order_by(Transaction.date.desc()).all()
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    next_due = loan.next_emi_date() if loan.status == 'active' else None
    return render_template(
        'loan_detail.html',
        loan=loan,
        payments=payments,
        accounts=accounts_list,
        next_due=next_due,
        today=date.today(),
    )


@loans_bp.route('/loan/<int:loan_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_loan(loan_id):
    loan = require_owner(Loan.query.get(loan_id))
    if request.method == 'POST':
        loan.name = request.form.get('name', '').strip() or loan.name
        loan.lender_type = request.form.get('lender_type', loan.lender_type)
        loan.principal = float(request.form.get('principal') or loan.principal)
        loan.outstanding = float(request.form.get('outstanding') or loan.outstanding)
        payment_mode = request.form.get('payment_mode', loan.payment_mode or 'emi')
        if payment_mode not in ('emi', 'one_time'):
            payment_mode = 'emi'
        loan.payment_mode = payment_mode
        if payment_mode == 'one_time':
            loan.emi_amount = 0.0
        else:
            loan.emi_amount = float(request.form.get('emi_amount') or 0)
        loan.interest_rate = float(request.form.get('interest_rate') or 0)
        loan.emi_day = max(1, min(28, int(request.form.get('emi_day') or 1)))
        tenure_value, tenure_unit = _parse_tenure(request.form)
        loan.tenure_value = tenure_value
        loan.tenure_unit = tenure_unit
        loan.notes = request.form.get('notes', '').strip()
        start_str = request.form.get('start_date')
        if start_str:
            try:
                loan.start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        status = request.form.get('status')
        if status in ('active', 'paid_off'):
            loan.status = status
            if status == 'paid_off':
                loan.outstanding = 0
        db.session.commit()
        flash('Loan updated.', 'success')
        return redirect(url_for('loans.loan_detail', loan_id=loan.id))
    return render_template('edit_loan.html', loan=loan)


@loans_bp.route('/loan/<int:loan_id>/delete', methods=['POST'])
@login_required
def delete_loan(loan_id):
    loan = require_owner(Loan.query.get(loan_id))
    for tx in Transaction.query.filter_by(loan_id=loan.id).all():
        tx.loan_id = None
    db.session.delete(loan)
    db.session.commit()
    flash('Loan deleted.', 'success')
    return redirect(url_for('loans.loans'))


@loans_bp.route('/loan/<int:loan_id>/pay_emi', methods=['POST'])
@login_required
def pay_emi(loan_id):
    loan = require_owner(Loan.query.get(loan_id))
    if loan.status != 'active':
        flash('Loan already paid off.', 'info')
        return redirect(url_for('loans.loan_detail', loan_id=loan.id))
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if not accounts_list:
        flash('Create a bank/cash account first.', 'warning')
        return redirect(url_for('accounts.add_account'))
    account_id = int(request.form.get('account_id'))
    amount = float(request.form.get('amount') or loan.emi_amount or 0)
    pay_status = request.form.get('status', 'completed')
    due_date_str = request.form.get('due_date')
    notes = request.form.get('notes', '').strip()
    if amount <= 0:
        flash('Amount must be positive.', 'danger')
        return redirect(url_for('loans.loan_detail', loan_id=loan.id))
    account = require_owner(Account.query.get(account_id))
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if due_date is None and pay_status == 'pending':
        due_date = loan.next_emi_date()
    amount = min(amount, loan.outstanding)
    mode = loan.payment_mode or 'emi'
    prefix = 'EMI' if mode == 'emi' else 'Repayment'
    desc = f'{prefix} – {loan.name}'
    if notes:
        desc = f'{desc} ({notes})'
    category = {
        'bank': 'Loan EMI',
        'friend': 'Friend Loan',
        'credit_card': 'Credit Card',
        'other': 'Loan',
    }.get(loan.lender_type, 'Loan')
    category = ensure_category(current_user.id, category)
    if pay_status == 'completed':
        account.balance -= amount
        loan.outstanding = max(0.0, loan.outstanding - amount)
        if loan.outstanding <= 0:
            loan.outstanding = 0
            loan.status = 'paid_off'
    tx = Transaction(
        description=desc,
        amount=amount,
        type='expense',
        status=pay_status,
        category=category,
        due_date=due_date,
        account_id=account_id,
        user_id=current_user.id,
        loan_id=loan.id,
    )
    db.session.add(tx)
    db.session.commit()
    if pay_status == 'pending':
        flash(f'EMI Rs {amount:.2f} added as pending.', 'info')
        return redirect(url_for('transactions.pending_payments'))
    flash(f'EMI Rs {amount:.2f} recorded. Outstanding: Rs {loan.outstanding:.2f}', 'success')
    return redirect(url_for('loans.loan_detail', loan_id=loan.id))


@loans_bp.route('/loan/<int:loan_id>/create_pending_emi', methods=['POST'])
@login_required
def create_pending_emi(loan_id):
    loan = require_owner(Loan.query.get(loan_id))
    if loan.status != 'active' or not loan.emi_amount:
        flash('No EMI amount set.', 'warning')
        return redirect(url_for('loans.loan_detail', loan_id=loan.id))
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if not accounts_list:
        flash('Create an account first.', 'warning')
        return redirect(url_for('accounts.add_account'))
    account_id = int(request.form.get('account_id') or accounts_list[0].id)
    amount = min(loan.emi_amount, loan.outstanding)
    due = loan.next_emi_date()
    category = {
        'bank': 'Loan EMI',
        'friend': 'Friend Loan',
        'credit_card': 'Credit Card',
        'other': 'Loan',
    }.get(loan.lender_type, 'Loan')
    category = ensure_category(current_user.id, category)
    tx = Transaction(
        description=f'EMI – {loan.name}',
        amount=amount,
        type='expense',
        status='pending',
        category=category,
        due_date=due,
        account_id=account_id,
        user_id=current_user.id,
        loan_id=loan.id,
    )
    db.session.add(tx)
    db.session.commit()
    flash(f'Pending EMI Rs {amount:.2f} for "{loan.name}" due {due.strftime("%d %b %Y")}.', 'info')
    return redirect(url_for('transactions.pending_payments'))
