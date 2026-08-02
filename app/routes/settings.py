from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.services.email import is_mail_configured, send_email
from app.security import validate_email, clamp_text, generate_api_token, hash_api_token

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        email_raw = clamp_text(request.form.get('email'), 120) or None
        ok, err = validate_email(email_raw)
        if not ok:
            flash(err, 'danger')
            return redirect(url_for('settings.settings'))
        current_user.email = email_raw
        db.session.commit()
        flash('Settings saved.', 'success')
        return redirect(url_for('settings.settings'))

    new_token = session.pop('new_api_token', None)
    return render_template(
        'settings.html',
        mail_configured=is_mail_configured(),
        new_api_token=new_token,
    )


@settings_bp.route('/settings/test_email', methods=['POST'])
@login_required
@limiter.limit('5 per hour')
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


@settings_bp.route('/settings/api_token/generate', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def generate_token():
    token = generate_api_token()
    current_user.api_token_hash = hash_api_token(token)
    current_user.api_token_prefix = token[:8]
    db.session.commit()
    session['new_api_token'] = token
    flash('API token generated. Copy it now — it will not be shown again.', 'warning')
    return redirect(url_for('settings.settings'))


@settings_bp.route('/settings/api_token/revoke', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def revoke_token():
    current_user.api_token_hash = None
    current_user.api_token_prefix = None
    db.session.commit()
    session.pop('new_api_token', None)
    flash('API token revoked. Existing integrations will stop working.', 'success')
    return redirect(url_for('settings.settings'))
