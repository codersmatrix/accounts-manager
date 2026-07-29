from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Account, Transaction, Investment

investments_bp = Blueprint('investments', __name__)


@investments_bp.route('/investments')
@login_required
def investments():
    active = Investment.query.filter_by(user_id=current_user.id, status='active').order_by(Investment.name).all()
    stopped = Investment.query.filter_by(user_id=current_user.id, status='stopped').order_by(Investment.name).all()
    total_invested = sum(i.total_invested for i in active) + sum(i.total_invested for i in stopped)
    monthly_sip = sum(i.monthly_sip for i in active if i.monthly_sip)
    return render_template(
        'investments.html',
        active=active,
        stopped=stopped,
        total_invested=total_invested,
        monthly_sip=monthly_sip,
        today=date.today(),
    )


@investments_bp.route('/add_investment', methods=['GET', 'POST'])
@login_required
def add_investment():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        monthly_sip = float(request.form.get('monthly_sip') or 0)
        if not name:
            flash('Name is required.', 'danger')
            return redirect(url_for('investments.add_investment'))
        sip_day = max(1, min(28, int(request.form.get('sip_day') or 1)))
        start_date = None
        start_str = request.form.get('start_date')
        if start_str:
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        inv = Investment(
            name=name,
            inv_type=request.form.get('inv_type', 'mutual_fund'),
            monthly_sip=monthly_sip,
            sip_day=sip_day,
            total_invested=float(request.form.get('total_invested') or 0),
            status='active',
            notes=request.form.get('notes', '').strip(),
            start_date=start_date,
            user_id=current_user.id,
        )
        db.session.add(inv)
        db.session.commit()
        flash(f'Investment "{name}" added.', 'success')
        return redirect(url_for('investments.investments'))
    return render_template('add_investment.html')


@investments_bp.route('/investment/<int:inv_id>')
@login_required
def investment_detail(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments.investments'))
    payments = Transaction.query.filter_by(investment_id=inv.id).order_by(Transaction.date.desc()).all()
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    next_sip = inv.next_sip_date() if inv.status == 'active' and inv.monthly_sip else None
    return render_template(
        'investment_detail.html',
        inv=inv,
        payments=payments,
        accounts=accounts_list,
        next_sip=next_sip,
        today=date.today(),
    )


@investments_bp.route('/investment/<int:inv_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_investment(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments.investments'))
    if request.method == 'POST':
        inv.name = request.form.get('name', '').strip() or inv.name
        inv.inv_type = request.form.get('inv_type', inv.inv_type)
        inv.monthly_sip = float(request.form.get('monthly_sip') or 0)
        inv.sip_day = max(1, min(28, int(request.form.get('sip_day') or 1)))
        inv.total_invested = float(request.form.get('total_invested') or inv.total_invested)
        inv.notes = request.form.get('notes', '').strip()
        start_str = request.form.get('start_date')
        if start_str:
            try:
                inv.start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        status = request.form.get('status')
        if status in ('active', 'stopped'):
            inv.status = status
        db.session.commit()
        flash('Investment updated.', 'success')
        return redirect(url_for('investments.investment_detail', inv_id=inv.id))
    return render_template('edit_investment.html', inv=inv)


@investments_bp.route('/investment/<int:inv_id>/delete', methods=['POST'])
@login_required
def delete_investment(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments.investments'))
    for tx in Transaction.query.filter_by(investment_id=inv.id).all():
        tx.investment_id = None
    db.session.delete(inv)
    db.session.commit()
    flash('Investment deleted.', 'success')
    return redirect(url_for('investments.investments'))


@investments_bp.route('/investment/<int:inv_id>/record_sip', methods=['POST'])
@login_required
def record_sip(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments.investments'))
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if not accounts_list:
        flash('Create a bank/cash account first.', 'warning')
        return redirect(url_for('accounts.add_account'))
    account_id = int(request.form.get('account_id'))
    amount = float(request.form.get('amount') or inv.monthly_sip or 0)
    pay_status = request.form.get('status', 'completed')
    due_date_str = request.form.get('due_date')
    notes = request.form.get('notes', '').strip()
    if amount <= 0:
        flash('Amount must be positive.', 'danger')
        return redirect(url_for('investments.investment_detail', inv_id=inv.id))
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments.investments'))
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if due_date is None and pay_status == 'pending':
        due_date = inv.next_sip_date()
    desc = f'SIP – {inv.name}'
    if notes:
        desc = f'{desc} ({notes})'
    if pay_status == 'completed':
        account.balance -= amount
        inv.total_invested = (inv.total_invested or 0) + amount
    tx = Transaction(
        description=desc,
        amount=amount,
        type='expense',
        status=pay_status,
        category='Investment',
        due_date=due_date,
        account_id=account_id,
        user_id=current_user.id,
        investment_id=inv.id,
    )
    db.session.add(tx)
    db.session.commit()
    if pay_status == 'pending':
        flash(f'SIP Rs {amount:.2f} added as pending.', 'info')
        return redirect(url_for('transactions.pending_payments'))
    flash(f'SIP Rs {amount:.2f} recorded. Total invested: Rs {inv.total_invested:.2f}', 'success')
    return redirect(url_for('investments.investment_detail', inv_id=inv.id))


@investments_bp.route('/investment/<int:inv_id>/create_pending_sip', methods=['POST'])
@login_required
def create_pending_sip(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments.investments'))
    if inv.status != 'active' or not inv.monthly_sip:
        flash('No SIP amount set.', 'warning')
        return redirect(url_for('investments.investment_detail', inv_id=inv.id))
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if not accounts_list:
        flash('Create an account first.', 'warning')
        return redirect(url_for('accounts.add_account'))
    account_id = int(request.form.get('account_id') or accounts_list[0].id)
    amount = inv.monthly_sip
    due = inv.next_sip_date()
    tx = Transaction(
        description=f'SIP – {inv.name}',
        amount=amount,
        type='expense',
        status='pending',
        category='Investment',
        due_date=due,
        account_id=account_id,
        user_id=current_user.id,
        investment_id=inv.id,
    )
    db.session.add(tx)
    db.session.commit()
    flash(f'Pending SIP Rs {amount:.2f} for "{inv.name}" due {due.strftime("%d %b %Y")}.', 'info')
    return redirect(url_for('transactions.pending_payments'))
