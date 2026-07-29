"""Email sending and payment-reminder helpers."""
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

from flask import current_app

from app.models import Transaction


def is_mail_configured():
    return bool(
        current_app.config.get('MAIL_USERNAME')
        and current_app.config.get('MAIL_PASSWORD')
        and current_app.config.get('MAIL_DEFAULT_SENDER')
    )


def send_email(to_email, subject, html_body, text_body=None):
    """Send an email via SMTP. Returns (success: bool, error_message: str|None)."""
    if not is_mail_configured():
        return False, 'Email is not configured. Set MAIL_USERNAME, MAIL_PASSWORD and MAIL_DEFAULT_SENDER.'
    if not to_email:
        return False, 'No recipient email address.'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
    msg['To'] = to_email
    if text_body:
        msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(
            current_app.config['MAIL_SERVER'],
            current_app.config['MAIL_PORT'],
        ) as server:
            if current_app.config['MAIL_USE_TLS']:
                server.starttls()
            server.login(
                current_app.config['MAIL_USERNAME'],
                current_app.config['MAIL_PASSWORD'],
            )
            server.sendmail(
                current_app.config['MAIL_DEFAULT_SENDER'],
                to_email,
                msg.as_string(),
            )
        return True, None
    except Exception as e:
        return False, str(e)


def build_reminder_email(user, transactions):
    if len(transactions) == 1:
        tx = transactions[0]
        due = tx.due_date.strftime('%d %b %Y') if tx.due_date else 'No due date'
        subject = f'Payment Reminder: {tx.description} – Rs {tx.amount:.2f}'
        html = (
            f'<html><body style="font-family:Arial,sans-serif;">'
            f'<h2>Payment Reminder</h2><p>Hi {user.username},</p>'
            f'<p>{tx.description} – Rs {tx.amount:.2f} due {due}</p>'
            f'<p>Category: {tx.category} | Account: {tx.account.name}</p>'
            f'<p>– Accounts Manager</p></body></html>'
        )
        text = f'Payment reminder: {tx.description} – Rs {tx.amount:.2f} due {due}'
    else:
        total = sum(t.amount for t in transactions if t.type == 'expense')
        subject = f'Payment Reminders: {len(transactions)} pending (Rs {total:.2f})'
        rows = ''.join(
            f'<tr><td>{tx.description}</td>'
            f'<td>{tx.due_date.strftime("%d %b %Y") if tx.due_date else "-"}</td>'
            f'<td>Rs {tx.amount:.2f}</td></tr>'
            for tx in transactions
        )
        html = (
            f'<html><body style="font-family:Arial,sans-serif;">'
            f'<h2>Payment Reminders</h2><p>Hi {user.username},</p>'
            f'<p>{len(transactions)} pending totaling Rs {total:.2f}</p>'
            f'<table border="1" cellpadding="6">{rows}</table>'
            f'<p>– Accounts Manager</p></body></html>'
        )
        text = f'{len(transactions)} pending payments totaling Rs {total:.2f}.'
    return subject, html, text


def get_due_pending(user_id, days_ahead=None):
    if days_ahead is None:
        days_ahead = current_app.config['REMINDER_DAYS_AHEAD']
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    pending = Transaction.query.filter_by(
        user_id=user_id, status='pending', type='expense'
    ).all()
    return [t for t in pending if t.due_date and t.due_date <= cutoff]
