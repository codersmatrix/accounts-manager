from datetime import datetime
from app.extensions import db


class Transaction(db.Model):
    __tablename__ = 'transaction'

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

    def __repr__(self):
        return f'<Transaction {self.description} {self.amount}>'
