"""Accounts Manager application factory."""
import os

from flask import Flask

from app.config import config_by_name
from app.extensions import db, login_manager


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
    app.config.from_object(cfg)
    app.config['SQLALCHEMY_DATABASE_URI'] = cfg.database_uri()

    # Extensions
    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    from app.routes import register_blueprints
    register_blueprints(app)

    # Create tables
    with app.app_context():
        db.create_all()

    return app
