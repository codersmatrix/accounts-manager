from datetime import date

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Account, Transaction, Loan, Investment
from app.services.email import get_due_pending

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    total_balance = sum(a.balance for a in accounts)

    recent_transactions = (
        Transaction.query.filter_by(user_id=current_user.id, status='completed')
        .order_by(Transaction.date.desc())
        .limit(8)
        .all()
    )
    pending = (
        Transaction.query.filter_by(user_id=current_user.id, status='pending')
        .order_by(Transaction.due_date.asc().nullslast(), Transaction.date.desc())
        .all()
    )
    pending_total = sum(t.amount for t in pending if t.type == 'expense')
    due_soon = get_due_pending(current_user.id)

    active_loans = Loan.query.filter_by(user_id=current_user.id, status='active').all()
    total_debt = sum(l.outstanding for l in active_loans)
    monthly_emi = sum(
        l.emi_amount
        for l in active_loans
        if l.emi_amount and (l.payment_mode or 'emi') == 'emi'
    )
    today = date.today()
    upcoming_emis = []
    for loan in active_loans:
        if (
            (loan.payment_mode or 'emi') == 'emi'
            and loan.emi_amount
            and loan.emi_amount > 0
            and loan.outstanding > 0
        ):
            next_due = loan.next_emi_date(today)
            upcoming_emis.append({
                'loan': loan,
                'due_date': next_due,
                'amount': min(loan.emi_amount, loan.outstanding),
            })
    upcoming_emis.sort(key=lambda x: x['due_date'])

    active_investments = Investment.query.filter_by(
        user_id=current_user.id, status='active'
    ).all()
    total_invested = sum(i.total_invested for i in active_investments)
    monthly_sip = sum(i.monthly_sip for i in active_investments if i.monthly_sip)
    upcoming_sips = []
    for inv in active_investments:
        if inv.monthly_sip and inv.monthly_sip > 0:
            upcoming_sips.append({
                'inv': inv,
                'due_date': inv.next_sip_date(today),
                'amount': inv.monthly_sip,
            })
    upcoming_sips.sort(key=lambda x: x['due_date'])

    return render_template(
        'dashboard.html',
        accounts=accounts,
        total_balance=total_balance,
        transactions=recent_transactions,
        pending=pending,
        pending_total=pending_total,
        due_soon_count=len(due_soon),
        active_loans=active_loans,
        total_debt=total_debt,
        monthly_emi=monthly_emi,
        upcoming_emis=upcoming_emis[:6],
        total_invested=total_invested,
        monthly_sip=monthly_sip,
        upcoming_sips=upcoming_sips[:6],
    )
