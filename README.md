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
- SQLite locally / Postgres on Heroku

## Project structure

```
accounts_app/
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Config from environment
│   ├── extensions.py        # db, login_manager
│   ├── models/              # User, Account, Transaction, Loan, Investment
│   ├── routes/              # Blueprints (auth, dashboard, accounts, …)
│   └── services/            # Email & reminder helpers
├── templates/
├── static/                  # PWA manifest, SW, icons
├── wsgi.py                  # Production entry (gunicorn)
├── run.py                   # Local development
├── app.py                   # Thin compatibility shim
├── requirements.txt
├── Procfile
└── runtime.txt
```

## Quick start (local)

```bash
cd accounts_app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:5000**

Or: `python app.py` (same app via compatibility shim).

## Production

```bash
export FLASK_ENV=production
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
# optional: DATABASE_URL, MAIL_* 
gunicorn wsgi:app --bind 0.0.0.0:$PORT
```

Heroku `Procfile` already uses `gunicorn wsgi:app`.

See **[DEPLOY.md](DEPLOY.md)** for Heroku / Render / Railway.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Session secret (required in production) |
| `DATABASE_URL` | Postgres URL (optional; SQLite if unset) |
| `FLASK_ENV` | `development` or `production` |
| `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_DEFAULT_SENDER` | Email reminders |
| `MAIL_SERVER` / `MAIL_PORT` | SMTP (defaults: Gmail) |
| `REMINDER_DAYS_AHEAD` | Days before due to treat as “due soon” (default 3) |

## Notes

- First run creates SQLite `accounts.db` (or uses `DATABASE_URL`).
- After schema changes from an older monolith, delete the old DB so tables are recreated.

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

See **[DEPLOY.md](DEPLOY.md)** for image build, volumes, and registry deploy.

## Database migrations (Postgres / SQLite)

Schema is managed with **Flask-Migrate (Alembic)**.

```bash
# Apply all pending migrations
python scripts/db_upgrade.py

# Create a new migration after changing models
python scripts/db_migrate.py "describe change"

# Fresh DB
python scripts/db_init.py

# Existing DB created with old create_all (mark as current, no DDL)
python scripts/db_init.py --stamp

# Show current revision
python scripts/db_current.py
```

On Docker / production, set `AUTO_MIGRATE=true` (default). The entrypoint runs
`scripts/db_upgrade.py` before gunicorn, and the app factory also upgrades on boot.
