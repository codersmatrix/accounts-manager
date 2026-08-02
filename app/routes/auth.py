from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, current_app, session,
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db, limiter
from app.models import User
from app.services.analytics import log_event
from app.services.mfa import verify_code
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
