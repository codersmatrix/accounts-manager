"""
Backward-compatible entrypoint.

Prefer:
  - Local:  python run.py
  - Prod:   gunicorn wsgi:app

This module still works so existing docs/scripts keep running.
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
