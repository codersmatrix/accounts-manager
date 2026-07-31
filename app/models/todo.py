"""Todo items with optional recurring reminders."""
from datetime import date, datetime, timedelta
import calendar

from app.extensions import db

CADENCE_CHOICES = [
    ('once', 'One-time'),
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('monthly', 'Monthly'),
]


class Todo(db.Model):
    __tablename__ = 'todo'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.String(500), default='')
    cadence = db.Column(db.String(20), default='once')
    cadence_day = db.Column(db.Integer, nullable=True)
    next_due = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='open')
    last_reminded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def cadence_label(self):
        return dict(CADENCE_CHOICES).get(self.cadence, self.cadence or 'once')

    def is_overdue(self, on_date=None):
        on_date = on_date or date.today()
        return self.status == 'open' and self.next_due and self.next_due < on_date

    def is_due_today(self, on_date=None):
        on_date = on_date or date.today()
        return self.status == 'open' and self.next_due == on_date

    def advance_next_due(self, from_date=None):
        from_date = from_date or self.next_due or date.today()
        c = (self.cadence or 'once').lower()
        if c == 'daily':
            self.next_due = from_date + timedelta(days=1)
        elif c == 'weekly':
            target = self.cadence_day
            if target is None:
                target = from_date.weekday()
            target = max(0, min(6, int(target)))
            d = from_date + timedelta(days=1)
            while d.weekday() != target:
                d += timedelta(days=1)
            self.next_due = d
        elif c == 'monthly':
            day = self.cadence_day or from_date.day
            day = max(1, min(28, int(day)))
            y, m = from_date.year, from_date.month
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
            last = calendar.monthrange(y, m)[1]
            self.next_due = date(y, m, min(day, last))
        else:
            self.next_due = from_date

    def __repr__(self):
        return f'<Todo {self.title}>'
