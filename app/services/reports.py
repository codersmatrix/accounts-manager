"""Category spend reports and budget progress."""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime

from app.models import Transaction, Budget


def month_bounds(year: int, month: int):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def category_spend(user_id: int, year: int, month: int) -> dict:
    """Completed expense totals by category for the calendar month."""
    start, end = month_bounds(year, month)
    rows = (
        Transaction.query.filter_by(user_id=user_id, type='expense', status='completed')
        .filter(Transaction.date != None)
        .filter(Transaction.date >= datetime.combine(start, datetime.min.time()))
        .filter(Transaction.date <= datetime.combine(end, datetime.max.time()))
        .all()
    )
    by_cat = defaultdict(float)
    total = 0.0
    for t in rows:
        cat = (t.category or 'General').strip() or 'General'
        by_cat[cat] += float(t.amount or 0)
        total += float(t.amount or 0)
    return {'by_category': dict(by_cat), 'total': total, 'count': len(rows)}


def category_income(user_id: int, year: int, month: int) -> dict:
    start, end = month_bounds(year, month)
    rows = (
        Transaction.query.filter_by(user_id=user_id, type='income', status='completed')
        .filter(Transaction.date != None)
        .filter(Transaction.date >= datetime.combine(start, datetime.min.time()))
        .filter(Transaction.date <= datetime.combine(end, datetime.max.time()))
        .all()
    )
    by_cat = defaultdict(float)
    total = 0.0
    for t in rows:
        cat = (t.category or 'General').strip() or 'General'
        by_cat[cat] += float(t.amount or 0)
        total += float(t.amount or 0)
    return {'by_category': dict(by_cat), 'total': total, 'count': len(rows)}


def budget_progress(user_id: int, year: int, month: int) -> list:
    """Merge budgets with actual spend for the month."""
    spend = category_spend(user_id, year, month)['by_category']
    budgets = (
        Budget.query.filter_by(user_id=user_id, year=year, month=month)
        .order_by(Budget.category.asc())
        .all()
    )
    rows = []
    seen = set()
    for b in budgets:
        actual = float(spend.get(b.category, 0) or 0)
        limit = float(b.amount or 0)
        pct = (actual / limit * 100) if limit > 0 else 0
        rows.append({
            'id': b.id,
            'category': b.category,
            'budget': limit,
            'spent': actual,
            'remaining': limit - actual,
            'pct': min(pct, 999),
            'over': actual > limit if limit > 0 else False,
            'notes': b.notes,
        })
        seen.add(b.category)
    for cat, actual in sorted(spend.items(), key=lambda x: -x[1]):
        if cat in seen:
            continue
        rows.append({
            'id': None,
            'category': cat,
            'budget': 0,
            'spent': actual,
            'remaining': -actual,
            'pct': 0,
            'over': False,
            'notes': None,
            'no_budget': True,
        })
    return rows
