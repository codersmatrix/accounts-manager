# Accounts Manager

Production-ready **PWA** for personal finance: accounts, loans/EMIs, mutual-fund SIPs, pending payments, and email reminders.

Built with **Python + Flask** (application factory, blueprints, modular services).

## Features

- Accounts (bank, cash, credit card, wallet)
- Loans (bank, friend, credit card) with **EMI or one-time** repayment
- Investments / mutual fund **SIPs** with monthly autopay tracking
- Pending payments + mark paid
- Email payment reminders
- PWA (installable, offline shell)
- SQLite locally / Postgres on Heroku or Docker

## Project structure

```
accounts_app/
├── app/                   # Application factory, models, routes, services
├── templates/  static/
├── wsgi.py / run.py / app.py
├── Dockerfile / docker-compose.yml
├── requirements.txt / Procfile
└── DEPLOY.md
```

## Quick start (local)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:5000**

## Docker

```bash
cp .env.example .env    # set SECRET_KEY
docker compose up --build
# http://localhost:8000
```

With Postgres:

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build
```

## Production

```bash
export FLASK_ENV=production SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
gunicorn wsgi:app --bind 0.0.0.0:$PORT
```

See **[DEPLOY.md](DEPLOY.md)** for Heroku, Docker image publish, and env vars.
