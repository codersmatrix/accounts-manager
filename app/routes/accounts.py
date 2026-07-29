from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Account

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
        account = Account(
            name=request.form.get('name').strip(),
            account_type=request.form.get('account_type'),
            balance=float(request.form.get('balance') or 0),
            user_id=current_user.id,
        )
        db.session.add(account)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('accounts.accounts'))
    return render_template('add_account.html')
