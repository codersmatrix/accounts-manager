from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Account
from app.security import clamp_text, safe_float

accounts_bp = Blueprint('accounts', __name__)


@accounts_bp.route('/accounts')
@login_required
def accounts():
    return render_template(
        'accounts.html',
        accounts=Account.query.filter_by(user_id=current_user.id).all(),
    )


@accounts_bp.route('/add_account', methods=['GET', 'POST'])
@login_required
def add_account():
    if request.method == 'POST':
        name = clamp_text(request.form.get('name'), 100)
        if not name:
            flash('Account name is required.', 'danger')
            return redirect(url_for('accounts.add_account'))
        account_type = clamp_text(request.form.get('account_type'), 50) or 'Bank'
        allowed = {'Bank', 'Cash', 'Credit Card', 'Wallet', 'Investment'}
        if account_type not in allowed:
            account_type = 'Bank'
        account = Account(
            name=name,
            account_type=account_type,
            balance=safe_float(request.form.get('balance'), 0.0, min_v=-1e12, max_v=1e12),
            user_id=current_user.id,
        )
        db.session.add(account)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('accounts.accounts'))
    return render_template('add_account.html')
