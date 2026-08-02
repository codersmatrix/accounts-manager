from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db, limiter
from app.models import User
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

        # First registered user becomes admin
        make_admin = User.query.count() == 0
        user = User(
            username=username,
            email=email_raw,
            password_hash=generate_password_hash(password, method='scrypt'),
            is_admin=make_admin,
        )
        db.session.add(user)
        db.session.commit()
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
            login_user(user, remember=bool(request.form.get('remember')))
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('dashboard.dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
