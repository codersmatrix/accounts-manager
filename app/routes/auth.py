import hashlib
import secrets
from datetime import datetime, timedelta

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, current_app, session,
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db, limiter
from app.models import User
from app.services.analytics import log_event
from app.services.mfa import verify_code
from app.services.email import send_email, is_mail_configured
from app.security import (
    validate_username,
    validate_email,
    validate_password,
    registration_enabled,
    clamp_text,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
@registration_enabled
@limiter.limit('5 per minute;20 per hour')
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    if request.method == 'POST':
        username = clamp_text(request.form.get('username'), 80)
        email_raw = clamp_text(request.form.get('email'), 120) or None
        password = request.form.get('password') or ''

        ok, err = validate_username(username)
        if not ok:
            flash(err, 'danger')
            return redirect(url_for('auth.register'))
        ok, err = validate_email(email_raw)
        if not ok:
            flash(err, 'danger')
            return redirect(url_for('auth.register'))
        ok, err = validate_password(password)
        if not ok:
            flash(err, 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('auth.register'))

        make_admin = User.query.count() == 0
        user = User(
            username=username,
            email=email_raw,
            password_hash=generate_password_hash(password, method='scrypt'),
            is_admin=make_admin,
            created_at=datetime.utcnow(),
            is_active_flag=True,
        )
        db.session.add(user)
        db.session.commit()
        log_event('register', user_id=user.id, meta=user.username)
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config.get('RATELIMIT_LOGIN', '10 per minute;30 per hour'))
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    if request.method == 'POST':
        username = clamp_text(request.form.get('username'), 80)
        password = request.form.get('password') or ''
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('This account is disabled.', 'danger')
                return redirect(url_for('auth.login'))
            if user.mfa_enabled and user.mfa_secret:
                session['mfa_user_id'] = user.id
                session['mfa_remember'] = bool(request.form.get('remember'))
                session['mfa_next'] = request.args.get('next') or ''
                return redirect(url_for('auth.mfa_verify'))
            login_user(user, remember=bool(request.form.get('remember')))
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            log_event('login', user_id=user.id, meta=user.username)
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('dashboard.dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')


@auth_bp.route('/mfa', methods=['GET', 'POST'])
@limiter.limit('10 per minute;30 per hour')
def mfa_verify():
    user_id = session.get('mfa_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, user_id)
    if not user or not user.mfa_enabled or not user.mfa_secret:
        session.pop('mfa_user_id', None)
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code') or ''
        if verify_code(user.mfa_secret, code):
            remember = bool(session.pop('mfa_remember', False))
            next_page = session.pop('mfa_next', '') or ''
            session.pop('mfa_user_id', None)
            login_user(user, remember=remember)
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            log_event('login', user_id=user.id, meta=f'{user.username}+mfa')
            if next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('dashboard.dashboard'))
        flash('Invalid authenticator code. Try again.', 'danger')

    return render_template('mfa_verify.html', username=user.username)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('mfa_user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit('5 per minute;15 per hour')
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    if request.method == 'POST':
        identifier = clamp_text(request.form.get('identifier'), 120)
        generic = (
            'If an account with that username or email exists and has an email on file, '
            'a reset link has been sent.'
        )
        if not identifier:
            flash('Enter your username or email.', 'warning')
            return redirect(url_for('auth.forgot_password'))

        user = User.query.filter_by(username=identifier).first()
        if not user and '@' in identifier:
            user = User.query.filter(User.email.ilike(identifier)).first()

        if user and user.email and is_mail_configured():
            token = secrets.token_urlsafe(32)
            user.reset_token_hash = _hash_reset_token(token)
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            html = (
                f'<html><body style="font-family:Arial,sans-serif;">'
                f'<h2>Password reset</h2>'
                f'<p>Hi {user.username},</p>'
                f'<p>We received a request to reset your password. '
                f'This link expires in <strong>1 hour</strong>.</p>'
                f'<p><a href="{reset_url}">Reset your password</a></p>'
                f'<p>If you did not request this, you can ignore this email.</p>'
                f'<p style="color:#666;font-size:12px;">Or paste: {reset_url}</p>'
                f'</body></html>'
            )
            text = f'Reset your password (expires in 1 hour): {reset_url}'
            ok, err = send_email(user.email, 'Accounts Manager \u2013 Password reset', html, text)
            if not ok:
                user.reset_token_hash = None
                user.reset_token_expires = None
                db.session.commit()
                flash(f'Could not send email: {err}', 'danger')
                return redirect(url_for('auth.forgot_password'))
        elif not is_mail_configured():
            flash('Password reset is unavailable: email is not configured on the server.', 'warning')
            return redirect(url_for('auth.forgot_password'))

        flash(generic, 'info')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html', mail_ok=is_mail_configured())


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit('10 per minute;30 per hour')
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    if not token or len(token) > 200:
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    th = _hash_reset_token(token)
    user = User.query.filter_by(reset_token_hash=th).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        flash('Invalid or expired reset link. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''
        ok, err = validate_password(password)
        if not ok:
            flash(err, 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        user.password_hash = generate_password_hash(password, method='scrypt')
        user.reset_token_hash = None
        user.reset_token_expires = None
        db.session.commit()
        flash('Password updated. You can log in now.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')
