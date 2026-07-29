#!/usr/bin/env python3
"""Show current database migration revision."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)


def main():
    from app import create_app
    from flask_migrate import current

    os.environ['AUTO_MIGRATE'] = 'false'
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        print('Current revision:')
        current(directory='migrations')


if __name__ == '__main__':
    main()
