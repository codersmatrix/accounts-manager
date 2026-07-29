release: python scripts/db_upgrade.py
web: gunicorn wsgi:app --bind 0.0.0.0:$PORT
