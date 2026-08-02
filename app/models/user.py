from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    api_token_hash = db.Column(db.String(64), nullable=True, index=True)
    api_token_prefix = db.Column(db.String(12), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_active_flag = db.Column(db.Boolean, default=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)
    mfa_secret = db.Column(db.String(32), nullable=True)
    mfa_enabled = db.Column(db.Boolean, default=False)

    accounts = db.relationship('Account', backref='owner', lazy=True)
    transactions = db.relationship('Transaction', backref='owner', lazy=True)
    loans = db.relationship('Loan', backref='owner', lazy=True)
    investments = db.relationship('Investment', backref='owner', lazy=True)

    def has_api_token(self) -> bool:
        return bool(self.api_token_hash)

    @property
    def is_active(self):
        if self.is_active_flag is None:
            return True
        return bool(self.is_active_flag)

    def __repr__(self):
        return f'<User {self.username}>'
