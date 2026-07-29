"""Application configuration with production-safe defaults."""
import os
import secrets


def _require_secret_key():
    key = os.environ.get('SECRET_KEY', '').strip()
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'production':
        if not key or key in (
            'change-this-to-a-random-secret-key-in-production',
            'change-me',
            'change-me-in-production-use-a-long-random-string',
            'replace-with-a-long-random-string',
        ):
            raise RuntimeError(
                'SECRET_KEY must be set to a strong random value in production. '
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        if len(key) < 32:
            raise RuntimeError('SECRET_KEY must be at least 32 characters in production.')
        return key
    return key or secrets.token_hex(32)


class Config:
    SECRET_KEY = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('SESSION_LIFETIME_SECONDS', 28800))
    SESSION_REFRESH_EACH_REQUEST = True

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = SESSION_COOKIE_SECURE

    ALLOW_REGISTRATION = os.environ.get('ALLOW_REGISTRATION', 'true').lower() in ('1', 'true', 'yes')
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'http')
    FORCE_HTTPS = os.environ.get('FORCE_HTTPS', '').lower() in ('1', 'true', 'yes')

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = (
        os.environ.get('MAIL_DEFAULT_SENDER', '') or os.environ.get('MAIL_USERNAME', '')
    )
    REMINDER_DAYS_AHEAD = int(os.environ.get('REMINDER_DAYS_AHEAD', 3))

    MIN_PASSWORD_LENGTH = int(os.environ.get('MIN_PASSWORD_LENGTH', 10))
    MAX_USERNAME_LENGTH = 80
    MAX_TEXT_LENGTH = 300

    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200 per hour;50 per minute')
    RATELIMIT_LOGIN = os.environ.get('RATELIMIT_LOGIN', '10 per minute;30 per hour')
    RATELIMIT_REGISTER = os.environ.get('RATELIMIT_REGISTER', '5 per hour')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

    @staticmethod
    def database_uri():
        url = os.environ.get('DATABASE_URL')
        if url:
            if url.startswith('postgres://'):
                url = url.replace('postgres://', 'postgresql://', 1)
            return url
        return os.environ.get('SQLITE_URI', 'sqlite:///instance/accounts.db')

    @classmethod
    def init_secret(cls):
        cls.SECRET_KEY = _require_secret_key()


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False
    FORCE_HTTPS = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() in ('1', 'true', 'yes')
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    WTF_CSRF_SSL_STRICT = SESSION_COOKIE_SECURE
    FORCE_HTTPS = os.environ.get('FORCE_HTTPS', 'true').lower() in ('1', 'true', 'yes')
    PREFERRED_URL_SCHEME = 'https'


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
