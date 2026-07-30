"""Auto-calculate investment capital from opening + completed payments."""
from sqlalchemy import func

from app.extensions import db
from app.models import Transaction


def refresh_total_invested(inv) -> float:
    """Set inv.total_invested = opening_amount + sum(completed payments)."""
    paid = (
        db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0))
        .filter(
            Transaction.investment_id == inv.id,
            Transaction.status == 'completed',
        )
        .scalar()
    )
    paid = float(paid or 0)
    opening = float(inv.opening_amount or 0)
    inv.total_invested = opening + paid
    return inv.total_invested
