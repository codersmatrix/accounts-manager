"""Pick the best account for an SMS / API transaction."""
from __future__ import annotations

import re
from typing import Optional, Sequence

from app.models import Account

BANK_KEYWORDS = [
    ('hdfc', ['hdfc']),
    ('sbi', ['sbi', 'sbiinb', 'state bank']),
    ('icici', ['icici']),
    ('axis', ['axis', 'axisbk']),
    ('kotak', ['kotak']),
    ('yes bank', ['yesbk', 'yes bank']),
    ('idfc', ['idfc']),
    ('pnb', ['pnb']),
    ('bob', ['bob', 'bank of baroda']),
    ('canara', ['canara']),
    ('union', ['union bank', 'ubin']),
    ('indusind', ['indusind', 'indus']),
    ('federal', ['federal']),
    ('phonepe', ['phonepe', 'phonpe']),
    ('gpay', ['gpay', 'google pay', 'goog']),
    ('paytm', ['paytm']),
    ('amazon pay', ['amazon pay', 'amazonpay']),
]


def _norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (s or '').lower())


def resolve_account(
    accounts: Sequence[Account],
    *,
    account_id: Optional[int] = None,
    account_hint: Optional[str] = None,
    sender: Optional[str] = None,
    text: Optional[str] = None,
) -> Optional[Account]:
    if not accounts:
        return None

    by_id = {a.id: a for a in accounts}
    if account_id is not None and account_id in by_id:
        return by_id[account_id]

    if account_hint:
        hint = str(account_hint).strip()
        for a in accounts:
            if hint and hint in (a.name or ''):
                return a
        for a in accounts:
            digits = re.findall(r'\d{3,6}', a.name or '')
            if hint in digits:
                return a

    blob = f'{sender or ""} {text or ""}'.lower()
    blob_n = _norm(blob)

    scored = []
    for a in accounts:
        name_l = (a.name or '').lower()
        name_n = _norm(a.name or '')
        score = 0
        for label, keys in BANK_KEYWORDS:
            if any(k in blob or k in blob_n for k in keys):
                if any(k in name_l or k in name_n for k in keys) or label in name_l:
                    score += 10
        if account_hint and account_hint in (a.name or ''):
            score += 5
        if score:
            scored.append((score, a))
    if scored:
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return scored[0][1]

    def type_rank(a: Account) -> tuple:
        t = (a.account_type or '').lower()
        n = (a.name or '').lower()
        if any(x in t for x in ('bank', 'savings', 'current', 'salary')):
            return (0, a.id)
        if any(x in n for x in ('bank', 'hdfc', 'sbi', 'icici', 'axis', 'kotak')):
            return (1, a.id)
        if any(x in t for x in ('cash', 'wallet')):
            return (3, a.id)
        return (2, a.id)

    ordered = sorted(accounts, key=type_rank)
    return ordered[0]
