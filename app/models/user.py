from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)

    accounts = db.relationship('Account', backref='owner', lazy=True)
    transactions = db.relationship('Transaction', backref='owner', lazy=True)
    loans = db.relationship('Loan', backref='owner', lazy=True)
    investments = db.relationship('Investment', backref='owner', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'
