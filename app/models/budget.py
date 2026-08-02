"""Monthly category budgets."""
from app.extensions import db


class Budget(db.Model):
    __tablename__ = 'budget'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.String(200), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'category', 'year', 'month', name='uq_budget_user_cat_period'),
    )

    def __repr__(self):
        return f'<Budget {self.category} {self.year}-{self.month} {self.amount}>'
