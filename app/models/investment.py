import calendar
from datetime import date
from app.extensions import db


class Investment(db.Model):
    __tablename__ = 'investment'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    inv_type = db.Column(db.String(30), default='mutual_fund')
    monthly_sip = db.Column(db.Float, default=0.0)
    sip_day = db.Column(db.Integer, default=1)
    total_invested = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='active')  # active | stopped
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

    def __repr__(self):
        return f'<Investment {self.name}>'
