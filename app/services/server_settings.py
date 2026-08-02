"""Read/write global server settings (DB overrides env)."""
from flask import current_app

from app.extensions import db
from app.models import ServerSetting

SETTING_KEYS = [
    'mail_server',
    'mail_port',
    'mail_use_tls',
    'mail_username',
    'mail_password',
    'mail_default_sender',
    'reminder_days_ahead',
    'allow_registration',
]


def get_setting(key: str, default=None):
    row = ServerSetting.query.get(key)
    if row is not None and row.value is not None and row.value != '':
        return row.value
    return default


def set_setting(key: str, value):
    if value is None:
        value = ''
    value = str(value)
    row = ServerSetting.query.get(key)
    if row is None:
        row = ServerSetting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value
    return row


def get_all_settings() -> dict:
    cfg = current_app.config
    defaults = {
        'mail_server': cfg.get('MAIL_SERVER', 'smtp.gmail.com'),
        'mail_port': str(cfg.get('MAIL_PORT', 587)),
        'mail_use_tls': 'true' if cfg.get('MAIL_USE_TLS', True) else 'false',
        'mail_username': cfg.get('MAIL_USERNAME', '') or '',
        'mail_password': cfg.get('MAIL_PASSWORD', '') or '',
        'mail_default_sender': cfg.get('MAIL_DEFAULT_SENDER', '') or '',
        'reminder_days_ahead': str(cfg.get('REMINDER_DAYS_AHEAD', 3)),
        'allow_registration': 'true' if cfg.get('ALLOW_REGISTRATION', True) else 'false',
    }
    out = {}
    for key in SETTING_KEYS:
        db_val = get_setting(key)
        if db_val is not None and db_val != '':
            out[key] = db_val
        else:
            out[key] = defaults.get(key, '')
    return out


def mail_config() -> dict:
    s = get_all_settings()
    try:
        port = int(s.get('mail_port') or 587)
    except ValueError:
        port = 587
    use_tls = str(s.get('mail_use_tls', 'true')).lower() in ('1', 'true', 'yes', 'on')
    username = (s.get('mail_username') or '').strip()
    password = s.get('mail_password') or ''
    sender = (s.get('mail_default_sender') or username or '').strip()
    return {
        'server': (s.get('mail_server') or 'smtp.gmail.com').strip(),
        'port': port,
        'use_tls': use_tls,
        'username': username,
        'password': password,
        'sender': sender,
    }


def is_mail_configured() -> bool:
    m = mail_config()
    return bool(m['username'] and m['password'] and m['sender'])


def registration_allowed() -> bool:
    val = get_setting('allow_registration')
    if val is not None and val != '':
        return str(val).lower() in ('1', 'true', 'yes', 'on')
    return bool(current_app.config.get('ALLOW_REGISTRATION', True))
