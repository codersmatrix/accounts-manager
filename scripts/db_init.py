#!/usr/bin/env python3
"""Initialize database schema via migrations."""
import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)


def main():
    parser = argparse.ArgumentParser(description='Initialize or stamp the database')
    parser.add_argument('--stamp', action='store_true', help='Stamp head without running migrations')
    args = parser.parse_args()

    from app import create_app
    from flask_migrate import upgrade, stamp

    os.environ['AUTO_MIGRATE'] = 'false'
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        safe = uri.split('@')[-1] if '@' in uri else uri
        print(f'Database: {safe}')
        if args.stamp:
            stamp(directory='migrations', revision='head')
            print('Stamped database at head (no DDL executed).')
        else:
            upgrade(directory='migrations')
            print('Database initialized (upgrade head).')


if __name__ == '__main__':
    main()
