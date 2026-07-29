from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import calendar

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-to-a-random-secret-key-in-production')

database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///accounts.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', '') or os.environ.get('MAIL_USERNAME', '')
app.config['REMINDER_DAYS_AHEAD'] = int(os.environ.get('REMINDER_DAYS_AHEAD', 3))

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    accounts = db.relationship('Account', backref='owner', lazy=True)
    transactions = db.relationship('Transaction', backref='owner', lazy=True)
    loans = db.relationship('Loan', backref='owner', lazy=True)
    investments = db.relationship('Investment', backref='owner', lazy=True)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(50), default='Bank')
    balance = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='account', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default='completed')
    category = db.Column(db.String(50), default='General')
    due_date = db.Column(db.Date, nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    last_reminder_sent = db.Column(db.DateTime, nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'), nullable=True)
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'), nullable=True)

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    lender_type = db.Column(db.String(30), default='bank')
    payment_mode = db.Column(db.String(20), default='emi')  # emi | one_time
    principal = db.Column(db.Float, nullable=False)
    outstanding = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, default=0.0)
    emi_amount = db.Column(db.Float, default=0.0)
    emi_day = db.Column(db.Integer, default=1)
    start_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.String(300), default='')
    status = db.Column(db.String(20), default='active')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    payments = db.relationship('Transaction', backref='loan', lazy=True)

    def next_emi_date(self, from_date=None):
        if from_date is None:
            from_date = date.today()
        day = min(max(self.emi_day or 1, 1), 28)
        year, month = from_date.year, from_date.month
        last = calendar.monthrange(year, month)[1]
        candidate = date(year, month, min(day, last))
        if candidate < from_date:
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
            last = calendar.monthrange(year, month)[1]
            candidate = date(year, month, min(day, last))
        return candidate


class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)           # e.g. HDFC Flexi Cap
    inv_type = db.Column(db.String(30), default='mutual_fund') # mutual_fund, stocks, fd, ppf, other
    monthly_sip = db.Column(db.Float, default=0.0)             # SIP / autopay amount
    sip_day = db.Column(db.Integer, default=1)                 # day of month autopay
    total_invested = db.Column(db.Float, default=0.0)          # cumulative amount invested
    status = db.Column(db.String(20), default='active')        # active, stopped
    notes = db.Column(db.String(300), default='')
    start_date = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def next_sip_date(self, from_date=None):
        if from_date is None:
            from_date = date.today()
        day = min(max(self.sip_day or 1, 1), 28)
        year, month = from_date.year, from_date.month
        last = calendar.monthrange(year, month)[1]
        candidate = date(year, month, min(day, last))
        if candidate < from_date:
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
            last = calendar.monthrange(year, month)[1]
            candidate = date(year, month, min(day, last))
        return candidate

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def is_mail_configured():
    return bool(app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD') and app.config.get('MAIL_DEFAULT_SENDER'))

def send_email(to_email, subject, html_body, text_body=None):
    if not is_mail_configured():
        return False, 'Email is not configured.'
    if not to_email:
        return False, 'No recipient email address.'
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = app.config['MAIL_DEFAULT_SENDER']
    msg['To'] = to_email
    if text_body:
        msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))
    try:
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            if app.config['MAIL_USE_TLS']:
                server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.sendmail(app.config['MAIL_DEFAULT_SENDER'], to_email, msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)

def build_reminder_email(user, transactions):
    if len(transactions) == 1:
        tx = transactions[0]
        due = tx.due_date.strftime('%d %b %Y') if tx.due_date else 'No due date'
        subject = f'Payment Reminder: {tx.description} – Rs {tx.amount:.2f}'
        html = f'<html><body style="font-family:Arial,sans-serif;"><h2>Payment Reminder</h2><p>Hi {user.username},</p><p>{tx.description} – Rs {tx.amount:.2f} due {due}</p><p>Category: {tx.category} | Account: {tx.account.name}</p><p>– Accounts Manager</p></body></html>'
        text = f'Payment reminder: {tx.description} – Rs {tx.amount:.2f} due {due}'
    else:
        total = sum(t.amount for t in transactions if t.type == 'expense')
        subject = f'Payment Reminders: {len(transactions)} pending (Rs {total:.2f})'
        rows = ''.join(f'<tr><td>{tx.description}</td><td>{tx.due_date.strftime("%d %b %Y") if tx.due_date else "-"}</td><td>Rs {tx.amount:.2f}</td></tr>' for tx in transactions)
        html = f'<html><body style="font-family:Arial,sans-serif;"><h2>Payment Reminders</h2><p>Hi {user.username},</p><p>{len(transactions)} pending totaling Rs {total:.2f}</p><table border="1" cellpadding="6">{rows}</table><p>– Accounts Manager</p></body></html>'
        text = f'{len(transactions)} pending payments totaling Rs {total:.2f}.'
    return subject, html, text

def get_due_pending(user_id, days_ahead=None):
    if days_ahead is None:
        days_ahead = app.config['REMINDER_DAYS_AHEAD']
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    pending = Transaction.query.filter_by(user_id=user_id, status='pending', type='expense').all()
    return [t for t in pending if t.due_date and t.due_date <= cutoff]

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.email = request.form.get('email', '').strip() or None
        db.session.commit()
        flash('Settings saved.', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html', mail_configured=is_mail_configured())

@app.route('/settings/test_email', methods=['POST'])
@login_required
def test_email():
    if not current_user.email:
        flash('Please save your email address first.', 'warning')
        return redirect(url_for('settings'))
    ok, err = send_email(current_user.email, 'Accounts Manager – Test Email',
        f'<html><body><h2>Test Email</h2><p>Hi {current_user.username}, email works.</p></body></html>', 'Test email')
    flash(f'Test email sent to {current_user.email}' if ok else f'Failed: {err}', 'success' if ok else 'danger')
    return redirect(url_for('settings'))

@app.route('/dashboard')
@login_required
def dashboard():
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    total_balance = sum(a.balance for a in accounts)
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id, status='completed').order_by(Transaction.date.desc()).limit(8).all()
    pending = Transaction.query.filter_by(user_id=current_user.id, status='pending').order_by(Transaction.due_date.asc().nullslast(), Transaction.date.desc()).all()
    pending_total = sum(t.amount for t in pending if t.type == 'expense')
    due_soon = get_due_pending(current_user.id)
    active_loans = Loan.query.filter_by(user_id=current_user.id, status='active').all()
    total_debt = sum(l.outstanding for l in active_loans)
    monthly_emi = sum(l.emi_amount for l in active_loans if l.emi_amount and (l.payment_mode or 'emi') == 'emi')
    today = date.today()
    upcoming_emis = []
    for loan in active_loans:
        if (loan.payment_mode or 'emi') == 'emi' and loan.emi_amount and loan.emi_amount > 0 and loan.outstanding > 0:
            next_due = loan.next_emi_date(today)
            upcoming_emis.append({'loan': loan, 'due_date': next_due, 'amount': min(loan.emi_amount, loan.outstanding)})
    upcoming_emis.sort(key=lambda x: x['due_date'])

    active_investments = Investment.query.filter_by(user_id=current_user.id, status='active').all()
    total_invested = sum(i.total_invested for i in active_investments)
    monthly_sip = sum(i.monthly_sip for i in active_investments if i.monthly_sip)
    upcoming_sips = []
    for inv in active_investments:
        if inv.monthly_sip and inv.monthly_sip > 0:
            upcoming_sips.append({'inv': inv, 'due_date': inv.next_sip_date(today), 'amount': inv.monthly_sip})
    upcoming_sips.sort(key=lambda x: x['due_date'])

    return render_template('dashboard.html', accounts=accounts, total_balance=total_balance, transactions=recent_transactions, pending=pending, pending_total=pending_total, due_soon_count=len(due_soon), active_loans=active_loans, total_debt=total_debt, monthly_emi=monthly_emi, upcoming_emis=upcoming_emis[:6], total_invested=total_invested, monthly_sip=monthly_sip, upcoming_sips=upcoming_sips[:6])

@app.route('/accounts')
@login_required
def accounts():
    return render_template('accounts.html', accounts=Account.query.filter_by(user_id=current_user.id).all())

@app.route('/add_account', methods=['GET', 'POST'])
@login_required
def add_account():
    if request.method == 'POST':
        account = Account(name=request.form.get('name').strip(), account_type=request.form.get('account_type'), balance=float(request.form.get('balance') or 0), user_id=current_user.id)
        db.session.add(account)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('accounts'))
    return render_template('add_account.html')

@app.route('/transactions')
@login_required
def transactions():
    status_filter = request.args.get('status', 'all')
    query = Transaction.query.filter_by(user_id=current_user.id)
    if status_filter == 'pending':
        query = query.filter_by(status='pending')
    elif status_filter == 'completed':
        query = query.filter_by(status='completed')
    return render_template('transactions.html', transactions=query.order_by(Transaction.date.desc()).all(), status_filter=status_filter)

@app.route('/pending')
@login_required
def pending_payments():
    pending = Transaction.query.filter_by(user_id=current_user.id, status='pending').order_by(Transaction.due_date.asc().nullslast(), Transaction.date.desc()).all()
    pending_total = sum(t.amount for t in pending if t.type == 'expense')
    return render_template('pending.html', pending=pending, pending_total=pending_total, due_soon_count=len(get_due_pending(current_user.id)), mail_configured=is_mail_configured(), today=date.today())

@app.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        account_id = int(request.form.get('account_id'))
        amount = float(request.form.get('amount'))
        tx_type = request.form.get('type')
        description = request.form.get('description').strip()
        category = request.form.get('category') or 'General'
        status = request.form.get('status', 'completed')
        due_date_str = request.form.get('due_date')
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        account = Account.query.get_or_404(account_id)
        if account.user_id != current_user.id:
            flash('Unauthorized', 'danger')
            return redirect(url_for('dashboard'))
        if status == 'completed':
            if tx_type == 'income':
                account.balance += amount
            else:
                account.balance -= amount
        tx = Transaction(description=description, amount=amount, type=tx_type, status=status, category=category, due_date=due_date, account_id=account_id, user_id=current_user.id)
        db.session.add(tx)
        db.session.commit()
        if status == 'pending':
            flash('Pending payment added.', 'info')
            return redirect(url_for('pending_payments'))
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('transactions'))
    return render_template('add_transaction.html', accounts=accounts_list)

@app.route('/mark_paid/<int:tx_id>', methods=['POST'])
@login_required
def mark_paid(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if tx.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard'))
    if tx.status != 'pending':
        flash('Already completed.', 'warning')
        return redirect(url_for('pending_payments'))
    account = Account.query.get(tx.account_id)
    if tx.type == 'income':
        account.balance += tx.amount
    else:
        account.balance -= tx.amount
    if tx.loan_id:
        loan = Loan.query.get(tx.loan_id)
        if loan and loan.user_id == current_user.id:
            loan.outstanding = max(0.0, loan.outstanding - tx.amount)
            if loan.outstanding <= 0:
                loan.outstanding = 0
                loan.status = 'paid_off'
    if tx.investment_id:
        inv = Investment.query.get(tx.investment_id)
        if inv and inv.user_id == current_user.id:
            inv.total_invested = (inv.total_invested or 0) + tx.amount
    tx.status = 'completed'
    tx.date = datetime.utcnow()
    db.session.commit()
    flash(f'"{tx.description}" marked as paid.', 'success')
    return redirect(url_for('pending_payments'))

@app.route('/delete_transaction/<int:tx_id>', methods=['POST'])
@login_required
def delete_transaction(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if tx.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard'))
    if tx.status == 'completed':
        account = Account.query.get(tx.account_id)
        if tx.type == 'income':
            account.balance -= tx.amount
        else:
            account.balance += tx.amount
        if tx.loan_id:
            loan = Loan.query.get(tx.loan_id)
            if loan and loan.user_id == current_user.id:
                loan.outstanding += tx.amount
                if loan.status == 'paid_off' and loan.outstanding > 0:
                    loan.status = 'active'
        if tx.investment_id:
            inv = Investment.query.get(tx.investment_id)
            if inv and inv.user_id == current_user.id:
                inv.total_invested = max(0.0, (inv.total_invested or 0) - tx.amount)
    db.session.delete(tx)
    db.session.commit()
    flash('Transaction deleted.', 'success')
    return redirect(request.referrer or url_for('transactions'))

@app.route('/send_reminder/<int:tx_id>', methods=['POST'])
@login_required
def send_reminder(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if tx.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('pending_payments'))
    if not current_user.email:
        flash('Set your email in Settings first.', 'warning')
        return redirect(url_for('settings'))
    subject, html, text = build_reminder_email(current_user, [tx])
    ok, err = send_email(current_user.email, subject, html, text)
    if ok:
        tx.last_reminder_sent = datetime.utcnow()
        db.session.commit()
        flash(f'Reminder sent for "{tx.description}".', 'success')
    else:
        flash(f'Failed: {err}', 'danger')
    return redirect(url_for('pending_payments'))

@app.route('/send_due_reminders', methods=['POST'])
@login_required
def send_due_reminders():
    if not current_user.email:
        flash('Set your email in Settings first.', 'warning')
        return redirect(url_for('settings'))
    due = get_due_pending(current_user.id)
    if not due:
        flash('No due/upcoming payments to remind.', 'info')
        return redirect(url_for('pending_payments'))
    subject, html, text = build_reminder_email(current_user, due)
    ok, err = send_email(current_user.email, subject, html, text)
    if ok:
        now = datetime.utcnow()
        for tx in due:
            tx.last_reminder_sent = now
        db.session.commit()
        flash(f'Reminders sent for {len(due)} payment(s).', 'success')
    else:
        flash(f'Failed: {err}', 'danger')
    return redirect(url_for('pending_payments'))

@app.route('/loans')
@login_required
def loans():
    active = Loan.query.filter_by(user_id=current_user.id, status='active').order_by(Loan.name).all()
    paid = Loan.query.filter_by(user_id=current_user.id, status='paid_off').order_by(Loan.name).all()
    return render_template('loans.html', active_loans=active, paid_loans=paid, total_debt=sum(l.outstanding for l in active), monthly_emi=sum(l.emi_amount for l in active if l.emi_amount and (l.payment_mode or 'emi') == 'emi'), today=date.today())

@app.route('/add_loan', methods=['GET', 'POST'])
@login_required
def add_loan():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        principal = float(request.form.get('principal') or 0)
        outstanding_raw = request.form.get('outstanding')
        outstanding = float(outstanding_raw) if outstanding_raw not in (None, '') else principal
        if not name or principal <= 0:
            flash('Name and positive principal required.', 'danger')
            return redirect(url_for('add_loan'))
        emi_day = max(1, min(28, int(request.form.get('emi_day') or 1)))
        start_date = None
        start_str = request.form.get('start_date')
        if start_str:
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        payment_mode = request.form.get('payment_mode', 'emi')
        if payment_mode not in ('emi', 'one_time'):
            payment_mode = 'emi'
        if payment_mode == 'one_time':
            emi_amount = 0.0
        else:
            emi_amount = float(request.form.get('emi_amount') or 0)
        loan = Loan(name=name, lender_type=request.form.get('lender_type', 'bank'), payment_mode=payment_mode, principal=principal, outstanding=outstanding, interest_rate=float(request.form.get('interest_rate') or 0), emi_amount=emi_amount, emi_day=emi_day, start_date=start_date, notes=request.form.get('notes', '').strip(), status='active', user_id=current_user.id)
        db.session.add(loan)
        db.session.commit()
        flash(f'Loan "{name}" added.', 'success')
        return redirect(url_for('loans'))
    return render_template('add_loan.html')

@app.route('/loan/<int:loan_id>')
@login_required
def loan_detail(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    if loan.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('loans'))
    payments = Transaction.query.filter_by(loan_id=loan.id).order_by(Transaction.date.desc()).all()
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    next_due = loan.next_emi_date() if loan.status == 'active' else None
    return render_template('loan_detail.html', loan=loan, payments=payments, accounts=accounts_list, next_due=next_due, today=date.today())

@app.route('/loan/<int:loan_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    if loan.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('loans'))
    if request.method == 'POST':
        loan.name = request.form.get('name', '').strip() or loan.name
        loan.lender_type = request.form.get('lender_type', loan.lender_type)
        loan.principal = float(request.form.get('principal') or loan.principal)
        loan.outstanding = float(request.form.get('outstanding') or loan.outstanding)
        loan.interest_rate = float(request.form.get('interest_rate') or 0)
        payment_mode = request.form.get('payment_mode', loan.payment_mode or 'emi')
        if payment_mode not in ('emi', 'one_time'):
            payment_mode = 'emi'
        loan.payment_mode = payment_mode
        if payment_mode == 'one_time':
            loan.emi_amount = 0.0
        else:
            loan.emi_amount = float(request.form.get('emi_amount') or 0)
        loan.emi_day = max(1, min(28, int(request.form.get('emi_day') or 1)))
        loan.notes = request.form.get('notes', '').strip()
        start_str = request.form.get('start_date')
        if start_str:
            try:
                loan.start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        status = request.form.get('status')
        if status in ('active', 'paid_off'):
            loan.status = status
            if status == 'paid_off':
                loan.outstanding = 0
        db.session.commit()
        flash('Loan updated.', 'success')
        return redirect(url_for('loan_detail', loan_id=loan.id))
    return render_template('edit_loan.html', loan=loan)

@app.route('/loan/<int:loan_id>/delete', methods=['POST'])
@login_required
def delete_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    if loan.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('loans'))
    for tx in Transaction.query.filter_by(loan_id=loan.id).all():
        tx.loan_id = None
    db.session.delete(loan)
    db.session.commit()
    flash('Loan deleted.', 'success')
    return redirect(url_for('loans'))

@app.route('/loan/<int:loan_id>/pay_emi', methods=['POST'])
@login_required
def pay_emi(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    if loan.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('loans'))
    if loan.status != 'active':
        flash('Loan already paid off.', 'info')
        return redirect(url_for('loan_detail', loan_id=loan.id))
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if not accounts_list:
        flash('Create a bank/cash account first.', 'warning')
        return redirect(url_for('add_account'))
    account_id = int(request.form.get('account_id'))
    amount = float(request.form.get('amount') or loan.emi_amount or 0)
    pay_status = request.form.get('status', 'completed')
    due_date_str = request.form.get('due_date')
    notes = request.form.get('notes', '').strip()
    if amount <= 0:
        flash('Amount must be positive.', 'danger')
        return redirect(url_for('loan_detail', loan_id=loan.id))
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('loans'))
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if due_date is None and pay_status == 'pending':
        due_date = loan.next_emi_date()
    amount = min(amount, loan.outstanding)
    mode = loan.payment_mode or 'emi'
    prefix = 'EMI' if mode == 'emi' else 'Repayment'
    desc = f'{prefix} – {loan.name}'
    if notes:
        desc = f'{desc} ({notes})'
    category = {'bank': 'Loan EMI', 'friend': 'Friend Loan', 'credit_card': 'Credit Card', 'other': 'Loan'}.get(loan.lender_type, 'Loan')
    if pay_status == 'completed':
        account.balance -= amount
        loan.outstanding = max(0.0, loan.outstanding - amount)
        if loan.outstanding <= 0:
            loan.outstanding = 0
            loan.status = 'paid_off'
    tx = Transaction(description=desc, amount=amount, type='expense', status=pay_status, category=category, due_date=due_date, account_id=account_id, user_id=current_user.id, loan_id=loan.id)
    db.session.add(tx)
    db.session.commit()
    if pay_status == 'pending':
        flash(f'EMI Rs {amount:.2f} added as pending.', 'info')
        return redirect(url_for('pending_payments'))
    flash(f'EMI Rs {amount:.2f} recorded. Outstanding: Rs {loan.outstanding:.2f}', 'success')
    return redirect(url_for('loan_detail', loan_id=loan.id))

@app.route('/loan/<int:loan_id>/create_pending_emi', methods=['POST'])
@login_required
def create_pending_emi(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    if loan.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('loans'))
    if loan.status != 'active' or not loan.emi_amount:
        flash('No EMI amount set.', 'warning')
        return redirect(url_for('loan_detail', loan_id=loan.id))
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if not accounts_list:
        flash('Create an account first.', 'warning')
        return redirect(url_for('add_account'))
    account_id = int(request.form.get('account_id') or accounts_list[0].id)
    amount = min(loan.emi_amount, loan.outstanding)
    due = loan.next_emi_date()
    category = {'bank': 'Loan EMI', 'friend': 'Friend Loan', 'credit_card': 'Credit Card', 'other': 'Loan'}.get(loan.lender_type, 'Loan')
    tx = Transaction(description=f'EMI – {loan.name}', amount=amount, type='expense', status='pending', category=category, due_date=due, account_id=account_id, user_id=current_user.id, loan_id=loan.id)
    db.session.add(tx)
    db.session.commit()
    flash(f'Pending EMI Rs {amount:.2f} for "{loan.name}" due {due.strftime("%d %b %Y")}.', 'info')
    return redirect(url_for('pending_payments'))


# -------------------- Investments / SIPs --------------------
@app.route('/investments')
@login_required
def investments():
    active = Investment.query.filter_by(user_id=current_user.id, status='active').order_by(Investment.name).all()
    stopped = Investment.query.filter_by(user_id=current_user.id, status='stopped').order_by(Investment.name).all()
    total_invested = sum(i.total_invested for i in active) + sum(i.total_invested for i in stopped)
    monthly_sip = sum(i.monthly_sip for i in active if i.monthly_sip)
    return render_template('investments.html', active=active, stopped=stopped, total_invested=total_invested, monthly_sip=monthly_sip, today=date.today())

@app.route('/add_investment', methods=['GET', 'POST'])
@login_required
def add_investment():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        monthly_sip = float(request.form.get('monthly_sip') or 0)
        if not name:
            flash('Name is required.', 'danger')
            return redirect(url_for('add_investment'))
        sip_day = max(1, min(28, int(request.form.get('sip_day') or 1)))
        start_date = None
        start_str = request.form.get('start_date')
        if start_str:
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        inv = Investment(
            name=name,
            inv_type=request.form.get('inv_type', 'mutual_fund'),
            monthly_sip=monthly_sip,
            sip_day=sip_day,
            total_invested=float(request.form.get('total_invested') or 0),
            status='active',
            notes=request.form.get('notes', '').strip(),
            start_date=start_date,
            user_id=current_user.id,
        )
        db.session.add(inv)
        db.session.commit()
        flash(f'Investment "{name}" added.', 'success')
        return redirect(url_for('investments'))
    return render_template('add_investment.html')

@app.route('/investment/<int:inv_id>')
@login_required
def investment_detail(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments'))
    payments = Transaction.query.filter_by(investment_id=inv.id).order_by(Transaction.date.desc()).all()
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    next_sip = inv.next_sip_date() if inv.status == 'active' and inv.monthly_sip else None
    return render_template('investment_detail.html', inv=inv, payments=payments, accounts=accounts_list, next_sip=next_sip, today=date.today())

@app.route('/investment/<int:inv_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_investment(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments'))
    if request.method == 'POST':
        inv.name = request.form.get('name', '').strip() or inv.name
        inv.inv_type = request.form.get('inv_type', inv.inv_type)
        inv.monthly_sip = float(request.form.get('monthly_sip') or 0)
        inv.sip_day = max(1, min(28, int(request.form.get('sip_day') or 1)))
        inv.total_invested = float(request.form.get('total_invested') or inv.total_invested)
        inv.notes = request.form.get('notes', '').strip()
        start_str = request.form.get('start_date')
        if start_str:
            try:
                inv.start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        status = request.form.get('status')
        if status in ('active', 'stopped'):
            inv.status = status
        db.session.commit()
        flash('Investment updated.', 'success')
        return redirect(url_for('investment_detail', inv_id=inv.id))
    return render_template('edit_investment.html', inv=inv)

@app.route('/investment/<int:inv_id>/delete', methods=['POST'])
@login_required
def delete_investment(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments'))
    for tx in Transaction.query.filter_by(investment_id=inv.id).all():
        tx.investment_id = None
    db.session.delete(inv)
    db.session.commit()
    flash('Investment deleted.', 'success')
    return redirect(url_for('investments'))

@app.route('/investment/<int:inv_id>/record_sip', methods=['POST'])
@login_required
def record_sip(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments'))
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if not accounts_list:
        flash('Create a bank/cash account first.', 'warning')
        return redirect(url_for('add_account'))
    account_id = int(request.form.get('account_id'))
    amount = float(request.form.get('amount') or inv.monthly_sip or 0)
    pay_status = request.form.get('status', 'completed')
    due_date_str = request.form.get('due_date')
    notes = request.form.get('notes', '').strip()
    if amount <= 0:
        flash('Amount must be positive.', 'danger')
        return redirect(url_for('investment_detail', inv_id=inv.id))
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments'))
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if due_date is None and pay_status == 'pending':
        due_date = inv.next_sip_date()
    desc = f'SIP – {inv.name}'
    if notes:
        desc = f'{desc} ({notes})'
    if pay_status == 'completed':
        account.balance -= amount
        inv.total_invested = (inv.total_invested or 0) + amount
    tx = Transaction(description=desc, amount=amount, type='expense', status=pay_status, category='Investment', due_date=due_date, account_id=account_id, user_id=current_user.id, investment_id=inv.id)
    db.session.add(tx)
    db.session.commit()
    if pay_status == 'pending':
        flash(f'SIP Rs {amount:.2f} added as pending.', 'info')
        return redirect(url_for('pending_payments'))
    flash(f'SIP Rs {amount:.2f} recorded. Total invested: Rs {inv.total_invested:.2f}', 'success')
    return redirect(url_for('investment_detail', inv_id=inv.id))

@app.route('/investment/<int:inv_id>/create_pending_sip', methods=['POST'])
@login_required
def create_pending_sip(inv_id):
    inv = Investment.query.get_or_404(inv_id)
    if inv.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('investments'))
    if inv.status != 'active' or not inv.monthly_sip:
        flash('No SIP amount set.', 'warning')
        return redirect(url_for('investment_detail', inv_id=inv.id))
    accounts_list = Account.query.filter_by(user_id=current_user.id).all()
    if not accounts_list:
        flash('Create an account first.', 'warning')
        return redirect(url_for('add_account'))
    account_id = int(request.form.get('account_id') or accounts_list[0].id)
    amount = inv.monthly_sip
    due = inv.next_sip_date()
    tx = Transaction(description=f'SIP – {inv.name}', amount=amount, type='expense', status='pending', category='Investment', due_date=due, account_id=account_id, user_id=current_user.id, investment_id=inv.id)
    db.session.add(tx)
    db.session.commit()
    flash(f'Pending SIP Rs {amount:.2f} for "{inv.name}" due {due.strftime("%d %b %Y")}.', 'info')
    return redirect(url_for('pending_payments'))



# -------------------- PWA --------------------
@app.route('/manifest.json')
def pwa_manifest():
    return send_from_directory(app.static_folder, 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def pwa_service_worker():
    resp = make_response(send_from_directory(app.static_folder, 'sw.js'))
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
