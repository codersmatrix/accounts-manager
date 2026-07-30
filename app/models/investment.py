import calendar
from datetime import date
from app.extensions import db


INV_TYPES = [
    ('mutual_fund', 'Mutual Fund (SIP)'),
    ('stocks', 'Stocks'),
    ('fd', 'Fixed Deposit'),
    ('ppf', 'PPF / EPF'),
    ('startup', 'Startup / Business (no market returns)'),
    ('other', 'Other'),
]

INV_TYPE_LABELS = dict(INV_TYPES)


class Investment(db.Model):
    __tablename__ = 'investment'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    inv_type = db.Column(db.String(30), default='mutual_fund')
    tags = db.Column(db.String(300), default='')
    monthly_sip = db.Column(db.Float, default=0.0)
    sip_day = db.Column(db.Integer, default=1)
    opening_amount = db.Column(db.Float, default=0.0)
    total_invested = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='active')
    notes = db.Column(db.String(300), default='')
    start_date = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def type_label(self):
        return INV_TYPE_LABELS.get(self.inv_type, (self.inv_type or 'other').replace('_', ' ').title())

    def is_no_returns(self):
        return (self.inv_type or '') == 'startup'

    def tag_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    def has_tag(self, tag: str) -> bool:
        if not tag:
            return True
        needle = tag.strip().lower()
        return any(t.lower() == needle for t in self.tag_list())

    def contribution_label(self):
        if (self.inv_type or '') == 'startup':
            return 'Monthly capital'
        return 'Monthly SIP'

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


class InvestmentTag(db.Model):
    __tablename__ = 'investment_tag'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='uq_investment_tag_user_name'),
    )

    def __repr__(self):
        return f'<InvestmentTag {self.name}>'
