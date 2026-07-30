import calendar
from datetime import date
from app.extensions import db


class Loan(db.Model):
    __tablename__ = 'loan'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    lender_type = db.Column(db.String(30), default='bank')  # bank | friend | credit_card | other
    payment_mode = db.Column(db.String(20), default='emi')  # emi | one_time
    principal = db.Column(db.Float, nullable=False)
    outstanding = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, default=0.0)
    emi_amount = db.Column(db.Float, default=0.0)
    emi_day = db.Column(db.Integer, default=1)
    # Remaining tenure (balance tenure)
    tenure_value = db.Column(db.Integer, nullable=True)  # e.g. 24
    tenure_unit = db.Column(db.String(10), default='months')  # months | years
    start_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.String(300), default='')
    status = db.Column(db.String(20), default='active')  # active | paid_off
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    payments = db.relationship('Transaction', backref='loan', lazy=True)

    def tenure_in_months(self):
        """Balance tenure expressed in months (None if not set)."""
        if self.tenure_value is None:
            return None
        unit = (self.tenure_unit or 'months').lower()
        if unit == 'years':
            return int(self.tenure_value) * 12
        return int(self.tenure_value)

    def tenure_display(self):
        """Human-readable balance tenure, e.g. '24 months' or '3 years'."""
        if self.tenure_value is None:
            return '—'
        unit = (self.tenure_unit or 'months').lower()
        if unit not in ('months', 'years'):
            unit = 'months'
        n = int(self.tenure_value)
        label = unit if n != 1 else unit[:-1]  # month / year
        # Prefer original unit for display
        if unit == 'months' and n >= 12 and n % 12 == 0:
            y = n // 12
            return f'{y} year{"s" if y != 1 else ""} ({n} months)'
        return f'{n} {label if n == 1 else unit}'

    def next_emi_date(self, from_date=None):
        """Next EMI due date on or after from_date (default today)."""
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

    def __repr__(self):
        return f'<Loan {self.name}>'
