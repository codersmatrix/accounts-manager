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

## Deploy to Heroku / Vercel

See **[DEPLOY.md](DEPLOY.md)** for step-by-step instructions.
