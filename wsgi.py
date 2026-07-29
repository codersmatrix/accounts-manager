"""WSGI entrypoint for production (gunicorn, waitress, etc.)."""
import os

from app import create_app

app = create_app(os.environ.get('FLASK_ENV', 'production'))
