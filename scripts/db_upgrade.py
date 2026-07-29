#!/usr/bin/env python3
"""Apply all pending database migrations (alembic upgrade head).

Usage:
  python scripts/db_upgrade.py
  FLASK_ENV=production DATABASE_URL=postgresql://... python scripts/db_upgrade.py
"""
import os
import sys

# Project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.chdir(ROOT)


def main():
    from app import create_app
    from flask_migrate import upgrade

    # Avoid recursive auto-migrate while we explicitly upgrade
    os.environ['AUTO_MIGRATE'] = 'false'
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        print(f'Database: {app.config["SQLALCHEMY_DATABASE_URI"].split("@")[-1]}')
        upgrade(directory='migrations')
        print('Migrations applied: upgrade head OK')


if __name__ == '__main__':
    main()
