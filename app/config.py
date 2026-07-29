"""Application configuration."""
import os


class Config:
    """Base configuration loaded from environment variables."""

    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-to-a-random-secret-key-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail / SMTP
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = (
        os.environ.get('MAIL_DEFAULT_SENDER', '')
        or os.environ.get('MAIL_USERNAME', '')
    )
    REMINDER_DAYS_AHEAD = int(os.environ.get('REMINDER_DAYS_AHEAD', 3))

    @staticmethod
    def database_uri():
        url = os.environ.get('DATABASE_URL')
        if url:
            # Heroku-style postgres:// → SQLAlchemy postgresql://
            if url.startswith('postgres://'):
                url = url.replace('postgres://', 'postgresql://', 1)
            return url
        return 'sqlite:///accounts.db'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
