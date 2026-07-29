# Accounts Management Web App

A simple, ready-to-run personal/business accounts management web application built with **Python + Flask**.

## Features

- **PWA** – install on phone/desktop, works offline for cached pages, home-screen icon

- **Loans & EMIs** – bank loans, friend loans, credit card balances
- Track outstanding, monthly EMI, due day; record payments or add as pending
- Dashboard shows total debt + upcoming EMIs

- User registration & login (with optional email)
- Multiple accounts (Bank, Cash, Credit Card, Wallet, Investment)
- Income & Expense transactions
- **Pending Payments** – record bills to pay later (balance unchanged until marked paid)
- **Email payment reminders** – one-click or batch email for due/overdue pending payments
- Automatic balance updates when marked paid
- Dashboard with total balance + pending total + due-soon count
- Transaction history with filters (All / Completed / Pending)
- Settings page for email + SMTP test
- Clean Bootstrap 5 UI

## Requirements

- Python 3.8+
- pip

## Quick Start

```bash
unzip accounts_app.zip
cd accounts_app

python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**

## Email Payment Reminders

### 1. Set your email in the app

Register with an email, or go to **Settings** (gear icon) and save your email address.

### 2. Configure SMTP (required to send mail)

Edit the top of `app.py` (or set environment variables):

```python
app.config['MAIL_USERNAME'] = 'you@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-16-char-app-password'   # Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = 'you@gmail.com'
# Optional:
# app.config['MAIL_SERVER'] = 'smtp.gmail.com'
# app.config['MAIL_PORT'] = 587
# app.config['REMINDER_DAYS_AHEAD'] = 3   # treat as "due soon" within N days
```

**Gmail setup:**
1. Enable 2-Step Verification on your Google account
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Use that 16-character password as `MAIL_PASSWORD` (not your normal Gmail password)

Other providers (Outlook, Yahoo, custom SMTP) work the same way with their server/port.

### 3. Send reminders

On the **Pending** page:

- **Envelope icon** on a row → email reminder for that single payment
- **Email Due Reminders** button → emails all pending expenses that are overdue or due within the next few days (items need a due date)

You can also send a **Test Email** from Settings.

## How Pending Payments Work

1. Add transaction → Status = **Pending** → optional **Due Date**
2. Balance is **not** changed yet
3. Open **Pending** → **Mark Paid** when you pay → balance updates

## Notes

- SQLite database `accounts.db` is created on first run
- If upgrading from an older version, delete `accounts.db` (or `instance/`) so new columns (`email`, `status`, `due_date`, `last_reminder_sent`) are created
- Change `SECRET_KEY` before any production use

## Project Structure

```
accounts_app/
├── app.py
├── requirements.txt
├── README.md
└── templates/
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── accounts.html
    ├── add_account.html
    ├── transactions.html
    ├── add_transaction.html
    ├── pending.html
    └── settings.html
```

## Deploy to Heroku / Vercel

See **[DEPLOY.md](DEPLOY.md)** for step-by-step instructions.

- **Heroku** (recommended): uses Gunicorn + Postgres
- **Vercel**: possible but limited (needs external database; serverless constraints)
