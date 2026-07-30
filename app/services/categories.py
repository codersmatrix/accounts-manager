"""Category list and upsert helpers."""
from app.extensions import db
from app.models import Category, Transaction

DEFAULT_CATEGORIES = [
    'General',
    'Bills',
    'Rent',
    'Food',
    'Transport',
    'Shopping',
    'Entertainment',
    'Healthcare',
    'Education',
    'Salary',
    'Freelance',
    'Investment',
    'Loan EMI',
    'Friend Loan',
    'Credit Card',
    'Utilities',
    'Insurance',
    'Travel',
]


def ensure_defaults(user_id: int) -> None:
    """Seed default categories for a user if they have none yet."""
    existing = Category.query.filter_by(user_id=user_id).count()
    if existing:
        return
    for name in DEFAULT_CATEGORIES:
        db.session.add(Category(name=name, user_id=user_id))
    db.session.commit()


def list_categories(user_id: int):
    """Return sorted unique category names for the user."""
    ensure_defaults(user_id)
    from_table = {
        c.name for c in Category.query.filter_by(user_id=user_id).all() if c.name
    }
    from_tx = {
        t.category
        for t in Transaction.query.filter_by(user_id=user_id).with_entities(Transaction.category).distinct()
        if t.category
    }
    return sorted(from_table | from_tx, key=lambda s: s.lower())


def ensure_category(user_id: int, name: str) -> str:
    """Persist a category name for the user if new; return cleaned name."""
    name = (name or '').strip()[:50] or 'General'
    existing = Category.query.filter_by(user_id=user_id, name=name).first()
    if not existing:
        all_cats = Category.query.filter_by(user_id=user_id).all()
        for c in all_cats:
            if c.name.lower() == name.lower():
                return c.name
        db.session.add(Category(name=name, user_id=user_id))
        db.session.flush()
    return name
