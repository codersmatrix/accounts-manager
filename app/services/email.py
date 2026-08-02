"""Email sending and payment-reminder helpers."""
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

from flask import current_app

from app.models import Transaction


def is_mail_configured():
    from app.services.server_settings import is_mail_configured as _db_mail
    return _db_mail()


def send_email(to_email, subject, html_body, text_body=None):
    """Send an email via SMTP. Returns (success: bool, error_message: str|None)."""
    from app.services.server_settings import mail_config, is_mail_configured as _cfg_ok
    if not _cfg_ok():
        return False, 'Email is not configured. An admin must set SMTP under Admin → Server settings.'
    if not to_email:
        return False, 'No recipient email address.'

    m = mail_config()
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = m['sender']
    msg['To'] = to_email
    if text_body:
        msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(m['server'], m['port'], timeout=30) as server:
            if m['use_tls']:
                server.starttls()
            server.login(m['username'], m['password'])
            server.sendmail(m['sender'], to_email, msg.as_string())
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
        subject = f'Payment Reminders: {len(transactions)} items (Rs {total:.2f})'
        rows = ''.join(
            f'<tr><td>{t.description}</td><td>Rs {t.amount:.2f}</td>'
            f'<td>{t.due_date.strftime("%d %b") if t.due_date else "—"}</td></tr>'
            for t in transactions
        )
        html = (
            f'<html><body style="font-family:Arial,sans-serif;">' 
            f'<h2>Payment Reminders</h2><p>Hi {user.username},</p>'
            f'<table border="1" cellpadding="6" cellspacing="0">'
            f'<tr><th>Description</th><th>Amount</th><th>Due</th></tr>{rows}</table>'
            f'<p>Total: Rs {total:.2f}</p><p>– Accounts Manager</p></body></html>'
        )
        text = f'{len(transactions)} payment reminders totaling Rs {total:.2f}'
    return subject, html, text


def get_due_pending(user_id, days_ahead=None):
    if days_ahead is None:
        try:
            from app.services.server_settings import get_all_settings
            days_ahead = int(get_all_settings().get('reminder_days_ahead') or 3)
        except Exception:
            days_ahead = current_app.config.get('REMINDER_DAYS_AHEAD', 3)
    today = date.today()
    until = today + timedelta(days=days_ahead)
    return (
        Transaction.query.filter_by(user_id=user_id, status='pending')
        .filter(Transaction.due_date != None)
        .filter(Transaction.due_date <= until)
        .order_by(Transaction.due_date.asc())
        .all()
    )
