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
    start_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.String(300), default='')
    status = db.Column(db.String(20), default='active')  # active | paid_off
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    payments = db.relationship('Transaction', backref='loan', lazy=True)

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
