"""Input validation, ownership checks, and security helpers."""
import re
import hashlib
import secrets
from functools import wraps

from flask import abort, current_app, flash, redirect, url_for
from flask_login import current_user


USERNAME_RE = re.compile(r'^[a-zA-Z0-9_\-.]{3,80}$')
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def validate_username(username: str):
    if not username or not USERNAME_RE.match(username):
        return False, 'Username must be 3–80 chars: letters, numbers, _ - .'
    return True, None


def validate_email(email: str | None):
    if email is None or email == '':
        return True, None
    if len(email) > 120 or not EMAIL_RE.match(email):
        return False, 'Invalid email address.'
    return True, None


def validate_password(password: str | None):
    min_len = current_app.config.get('MIN_PASSWORD_LENGTH', 10)
    if not password or len(password) < min_len:
        return False, f'Password must be at least {min_len} characters.'
    if len(password) > 128:
        return False, 'Password is too long.'
    if password.strip() == '' or len(set(password)) < 3:
        return False, 'Password is too weak. Use a mix of characters.'
    return True, None


def clamp_text(value: str | None, max_len: int | None = None) -> str:
    if value is None:
        return ''
    max_len = max_len or current_app.config.get('MAX_TEXT_LENGTH', 300)
    return value.strip()[:max_len]


def safe_float(value, default=0.0, min_v=None, max_v=None):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    if min_v is not None and n < min_v:
        n = min_v
    if max_v is not None and n > max_v:
        n = max_v
    if n != n or n in (float('inf'), float('-inf')):
        return default
    return n


def safe_int(value, default=0, min_v=None, max_v=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if min_v is not None and n < min_v:
        n = min_v
    if max_v is not None and n > max_v:
        n = max_v
    return n


def require_owner(obj, user_id_attr='user_id'):
    """Abort 404 if object is missing or not owned (no IDOR leak)."""
    if obj is None:
        abort(404)
    if getattr(obj, user_id_attr, None) != current_user.id:
        abort(404)
    return obj


def registration_enabled(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        from app.services.server_settings import registration_allowed
        if not registration_allowed():
            flash('Registration is disabled.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped


def admin_required(f):
    """Require logged-in user with is_admin."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not getattr(current_user, 'is_admin', False):
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    return wrapped


def generate_api_token() -> str:
    """Return a new URL-safe API token (plaintext, show once)."""
    return secrets.token_urlsafe(32)


def hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def find_user_by_api_token(token: str):
    """Look up user by plaintext Bearer token. Returns User or None."""
    if not token or len(token) < 20 or len(token) > 200:
        return None
    from app.models import User
    th = hash_api_token(token.strip())
    return User.query.filter_by(api_token_hash=th).first()


def api_token_required(f):
    """Decorator: require Authorization: Bearer <token>. Sets g.api_user."""
    from flask import g, jsonify, request

    @wraps(f)
    def wrapped(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = None
        if auth.lower().startswith('bearer '):
            token = auth[7:].strip()
        if not token:
            token = request.headers.get('X-API-Token', '').strip() or None
        user = find_user_by_api_token(token) if token else None
        if not user:
            return jsonify({'error': 'unauthorized', 'message': 'Invalid or missing API token'}), 401
        g.api_user = user
        return f(*args, **kwargs)
    return wrapped
