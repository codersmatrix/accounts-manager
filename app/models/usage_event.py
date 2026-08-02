"""Usage / analytics events for admin insights."""
from datetime import datetime

from app.extensions import db


class UsageEvent(db.Model):
    __tablename__ = 'usage_event'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(40), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    path = db.Column(db.String(200), nullable=True)
    method = db.Column(db.String(10), nullable=True)
    meta = db.Column(db.String(200), nullable=True)
    ip = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True, nullable=False)

    def __repr__(self):
        return f'<UsageEvent {self.event_type} {self.path}>'
