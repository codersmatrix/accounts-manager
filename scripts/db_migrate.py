#!/usr/bin/env python3
"""Autogenerate a new Alembic migration from model changes.

Usage:
  python scripts/db_migrate.py "add foo column"
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)


def main():
    message = ' '.join(sys.argv[1:]) or 'auto migration'
    from app import create_app
    from flask_migrate import migrate as gen_migrate

    os.environ['AUTO_MIGRATE'] = 'false'
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        # Import models so metadata is complete
        import app.models  # noqa: F401
        gen_migrate(directory='migrations', message=message)
        print(f'Migration generated: {message!r}')


if __name__ == '__main__':
    main()
