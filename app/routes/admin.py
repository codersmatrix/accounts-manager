"""Admin: server-wide settings (SMTP, registration, etc.)."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db, limiter
from app.security import admin_required, clamp_text, safe_int
from app.services.server_settings import (
    get_all_settings,
    set_setting,
    is_mail_configured,
)
from app.services.email import send_email

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def server_settings():
    if request.method == 'POST':
        set_setting('mail_server', clamp_text(request.form.get('mail_server'), 120) or 'smtp.gmail.com')
        set_setting('mail_port', str(safe_int(request.form.get('mail_port'), 587, 1, 65535)))
        set_setting(
            'mail_use_tls',
            'true' if request.form.get('mail_use_tls') in ('on', 'true', '1', 'yes') else 'false',
        )
        set_setting('mail_username', clamp_text(request.form.get('mail_username'), 200))
        new_pw = request.form.get('mail_password') or ''
        if new_pw.strip():
            set_setting('mail_password', new_pw.strip())
        set_setting('mail_default_sender', clamp_text(request.form.get('mail_default_sender'), 200))
        set_setting(
            'reminder_days_ahead',
            str(safe_int(request.form.get('reminder_days_ahead'), 3, 0, 30)),
        )
        set_setting(
            'allow_registration',
            'true' if request.form.get('allow_registration') in ('on', 'true', '1', 'yes') else 'false',
        )
        db.session.commit()
        flash('Server settings saved.', 'success')
        return redirect(url_for('admin.server_settings'))

    settings = get_all_settings()
    has_password = bool(settings.get('mail_password'))
    settings_display = dict(settings)
    settings_display['mail_password'] = ''
    return render_template(
        'admin_settings.html',
        settings=settings_display,
        has_password=has_password,
        mail_configured=is_mail_configured(),
    )


@admin_bp.route('/settings/test_email', methods=['POST'])
@login_required
@admin_required
@limiter.limit('10 per hour')
def test_smtp():
    to_email = (request.form.get('test_to') or current_user.email or '').strip()
    if not to_email:
        flash('Enter a recipient email (or save your email in Settings).', 'warning')
        return redirect(url_for('admin.server_settings'))
    if not is_mail_configured():
        flash('Save SMTP settings first (username, password, sender).', 'warning')
        return redirect(url_for('admin.server_settings'))
    ok, err = send_email(
        to_email,
        'Accounts Manager – SMTP Test',
        f'<html><body><h2>SMTP works</h2><p>Hi {current_user.username}, server mail is configured correctly.</p></body></html>',
        'SMTP test email from Accounts Manager',
    )
    flash(f'Test email sent to {to_email}.' if ok else f'Test failed: {err}', 'success' if ok else 'danger')
    return redirect(url_for('admin.server_settings'))
