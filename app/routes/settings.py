from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.services.email import is_mail_configured, send_email

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.email = request.form.get('email', '').strip() or None
        db.session.commit()
        flash('Settings saved.', 'success')
        return redirect(url_for('settings.settings'))
    return render_template('settings.html', mail_configured=is_mail_configured())


@settings_bp.route('/settings/test_email', methods=['POST'])
@login_required
def test_email():
    if not current_user.email:
        flash('Please save your email address first.', 'warning')
        return redirect(url_for('settings.settings'))
    ok, err = send_email(
        current_user.email,
        'Accounts Manager – Test Email',
        f'<html><body><h2>Test Email</h2><p>Hi {current_user.username}, email works.</p></body></html>',
        'Test email',
    )
    flash(
        f'Test email sent to {current_user.email}' if ok else f'Failed: {err}',
        'success' if ok else 'danger',
    )
    return redirect(url_for('settings.settings'))
