"""Investment tag helpers: list + ensure new tags."""
from app.extensions import db
from app.models.investment import Investment, InvestmentTag

DEFAULT_TAGS = [
    'long-term',
    'tax-saving',
    'emergency',
    'growth',
    'income',
    'startup',
]


def list_tags(user_id: int):
    ensure_defaults(user_id)
    from_table = {
        t.name for t in InvestmentTag.query.filter_by(user_id=user_id).all() if t.name
    }
    from_inv = set()
    for inv in Investment.query.filter_by(user_id=user_id).all():
        from_inv.update(inv.tag_list())
    return sorted(from_table | from_inv, key=lambda s: s.lower())


def ensure_defaults(user_id: int) -> None:
    if InvestmentTag.query.filter_by(user_id=user_id).count():
        return
    for name in DEFAULT_TAGS:
        db.session.add(InvestmentTag(name=name, user_id=user_id))
    db.session.commit()


def normalize_tags(raw: str) -> str:
    if not raw:
        return ''
    parts = []
    seen = set()
    for p in raw.replace(';', ',').split(','):
        t = p.strip()[:50]
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        parts.append(t)
    return ', '.join(parts)[:300]


def ensure_tags(user_id: int, raw: str) -> str:
    cleaned = normalize_tags(raw)
    if not cleaned:
        return ''
    existing = {
        t.name.lower(): t.name
        for t in InvestmentTag.query.filter_by(user_id=user_id).all()
    }
    for part in cleaned.split(','):
        name = part.strip()
        if not name:
            continue
        if name.lower() not in existing:
            db.session.add(InvestmentTag(name=name, user_id=user_id))
            existing[name.lower()] = name
    db.session.flush()
    return cleaned
