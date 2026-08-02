"""Register all blueprints."""


def register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.accounts import accounts_bp
    from app.routes.transactions import transactions_bp
    from app.routes.loans import loans_bp
    from app.routes.investments import investments_bp
    from app.routes.settings import settings_bp
    from app.routes.pwa import pwa_bp
    from app.routes.todos import todos_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(loans_bp)
    app.register_blueprint(investments_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(todos_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(pwa_bp)
