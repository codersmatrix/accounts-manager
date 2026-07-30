"""Accounts Manager application factory."""
import os

from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import config_by_name
from app.extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
        if config_name not in config_by_name:
            config_name = 'default'

    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )
    cfg = config_by_name.get(config_name, config_by_name['default'])
    cfg.init_secret()
    app.config.from_object(cfg)
    app.config['SECRET_KEY'] = cfg.SECRET_KEY
    app.config['SQLALCHEMY_DATABASE_URI'] = cfg.database_uri()
    app.config['SESSION_COOKIE_SECURE'] = cfg.SESSION_COOKIE_SECURE
    app.config['REMEMBER_COOKIE_SECURE'] = cfg.REMEMBER_COOKIE_SECURE
    app.config['WTF_CSRF_SSL_STRICT'] = cfg.WTF_CSRF_SSL_STRICT

    # Trust X-Forwarded-* when behind reverse proxy / load balancer
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    app.config.setdefault(
        'RATELIMIT_STORAGE_URI',
        app.config.get('RATELIMIT_STORAGE_URI', 'memory://'),
    )
    limiter.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return None
        return db.session.get(User, uid)

    # Blueprints
    from app.routes import register_blueprints
    register_blueprints(app)

    # Security headers on every response
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=(), payment=()'
        )
        # CSP: allow self + Bootstrap CDN used by templates
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net data:; "
            "img-src 'self' data:; "
            #"connect-src 'self'; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        if app.config.get('FORCE_HTTPS') or app.config.get('SESSION_COOKIE_SECURE'):
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )
        # Do not cache authenticated HTML pages
        if response.content_type and 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
        return response

    @app.before_request
    def enforce_https():
        if app.config.get('FORCE_HTTPS') and not app.debug:
            # Honor proxy header set by ProxyFix
            if request.headers.get('X-Forwarded-Proto', 'http') == 'http' and not request.is_secure:
                url = request.url.replace('http://', 'https://', 1)
                from flask import redirect
                return redirect(url, code=301)

    # Safe error pages (no stack traces to clients)
    @app.errorhandler(400)
    def bad_request(e):
        return render_template('error.html', code=400, message='Bad request'), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('error.html', code=403, message='Forbidden'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', code=404, message='Page not found'), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template(
            'error.html', code=429, message='Too many requests. Please try again later.'
        ), 429

    @app.errorhandler(500)
    def server_error(e):
        return render_template('error.html', code=500, message='Something went wrong.'), 500

    if os.environ.get("VERCEL") != "1":
        os.makedirs(app.instance_path, exist_ok=True)

    # Schema management: prefer Alembic migrations over create_all
    auto_migrate = os.environ.get('AUTO_MIGRATE', 'true').lower() in ('1', 'true', 'yes')
    if auto_migrate:
        with app.app_context():
            _apply_migrations(app)

    return app


def _apply_migrations(app):
    """Apply pending Alembic migrations (upgrade to head).

    Safe to call on every startup. Falls back to create_all only if the
    migrations package is missing (dev edge case).
    """
    from flask import current_app
    try:
        from flask_migrate import upgrade
        upgrade(directory='migrations')
        current_app.logger.info('Database migrations applied (upgrade head).')
    except Exception as exc:
        current_app.logger.warning(
            'Migration upgrade failed (%s); falling back to db.create_all().',
            exc,
        )
        db.create_all()
