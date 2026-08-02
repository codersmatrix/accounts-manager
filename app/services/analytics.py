"""Record and aggregate usage events."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from flask import request, has_request_context
from flask_login import current_user

from app.extensions import db
from app.models import UsageEvent, User, Account, Transaction, Loan, Investment, Todo


SKIP_PREFIXES = (
    '/static/',
    '/sw.js',
    '/manifest.json',
    '/favicon',
)


def _client_ip() -> str | None:
    if not has_request_context():
        return None
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()[:45]
    return (request.remote_addr or '')[:45]


def log_event(event_type: str, *, path: str | None = None, method: str | None = None,
              meta: str | None = None, user_id: int | None = None) -> None:
    try:
        uid = user_id
        if uid is None and has_request_context():
            try:
                if current_user.is_authenticated:
                    uid = current_user.id
            except Exception:
                pass
        if path is None and has_request_context():
            path = (request.path or '')[:200]
        if method is None and has_request_context():
            method = (request.method or '')[:10]
        ev = UsageEvent(
            event_type=(event_type or 'unknown')[:40],
            user_id=uid,
            path=path,
            method=method,
            meta=(meta or '')[:200] or None,
            ip=_client_ip(),
            created_at=datetime.utcnow(),
        )
        db.session.add(ev)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def should_track_path(path: str) -> bool:
    if not path:
        return False
    for p in SKIP_PREFIXES:
        if path.startswith(p):
            return False
    return True


def system_counts() -> dict:
    return {
        'users': User.query.count(),
        'admins': User.query.filter_by(is_admin=True).count(),
        'accounts': Account.query.count(),
        'transactions': Transaction.query.count(),
        'pending_tx': Transaction.query.filter_by(status='pending').count(),
        'loans': Loan.query.count(),
        'investments': Investment.query.count(),
        'todos': Todo.query.count(),
    }


def analytics_summary(days: int = 7) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        UsageEvent.query.filter(UsageEvent.created_at >= since)
        .order_by(UsageEvent.created_at.desc())
        .limit(5000)
        .all()
    )
    by_type = defaultdict(int)
    by_day = defaultdict(int)
    by_path = defaultdict(int)
    api_calls = 0
    logins = 0
    for r in rows:
        by_type[r.event_type] += 1
        day = r.created_at.strftime('%Y-%m-%d') if r.created_at else 'unknown'
        by_day[day] += 1
        if r.event_type == 'page_view' and r.path:
            by_path[r.path] += 1
        if r.event_type == 'api_call':
            api_calls += 1
        if r.event_type == 'login':
            logins += 1

    top_paths = sorted(by_path.items(), key=lambda x: -x[1])[:15]
    days_series = sorted(by_day.items())
    max_day = max((n for _, n in days_series), default=0)

    recent_rows = (
        UsageEvent.query.order_by(UsageEvent.created_at.desc()).limit(40).all()
    )
    user_ids = {e.user_id for e in recent_rows if e.user_id}
    names = {}
    if user_ids:
        for u in User.query.filter(User.id.in_(user_ids)).all():
            names[u.id] = u.username
    recent = []
    for e in recent_rows:
        recent.append({
            'created_at': e.created_at,
            'event_type': e.event_type,
            'user_id': e.user_id,
            'username': names.get(e.user_id) if e.user_id else None,
            'path': e.path,
            'meta': e.meta,
            'method': e.method,
        })

    return {
        'days': days,
        'total_events': len(rows),
        'by_type': dict(sorted(by_type.items(), key=lambda x: -x[1])),
        'days_series': days_series,
        'max_day': max_day,
        'top_paths': top_paths,
        'api_calls': api_calls,
        'logins': logins,
        'recent': recent,
    }
