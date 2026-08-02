"""Parse bank / UPI SMS text into transaction fields.

Handles common Indian bank patterns (HDFC, SBI, ICICI, Axis, PhonePe, GPay, etc.).
Returns a dict or None if amount cannot be extracted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ParsedSms:
    amount: float
    tx_type: str  # expense | income
    description: str
    category: str
    merchant: Optional[str] = None
    account_hint: Optional[str] = None
    raw_matched: Optional[str] = None

    def to_dict(self):
        return asdict(self)


AMOUNT_RE = re.compile(
    r'(?:(?:inr|rs\.?|₹)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?))'
    r'|'
    r'([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*(?:inr|rs\.?|₹)',
    re.IGNORECASE,
)

DEBIT_WORDS = re.compile(
    r'\b(debited|debit|spent|paid|purchase|withdrawn|withdrawal|sent|deducted|dr\.?)\b',
    re.IGNORECASE,
)
CREDIT_WORDS = re.compile(
    r'\b(credited|credit|received|deposited|refund|cashback|cr\.?)\b',
    re.IGNORECASE,
)

MERCHANT_RE = re.compile(
    r'(?:'
    r'(?:at|to|towards|for|from)\s+([A-Za-z0-9][A-Za-z0-9 &._\-]{2,40}?)'
    r'(?=\s+(?:on|via|using|ref|upi|avl|info|sms|helpline|\.|$))'
    r'|'
    r'UPI[/\\-]([A-Za-z0-9.\-_]{3,40})'
    r'|'
    r'VPA\s+([A-Za-z0-9.\-_@]{3,40})'
    r')',
    re.IGNORECASE,
)

ACCOUNT_RE = re.compile(
    r'(?:a/?c|account|acct|xx|x{2,})\s*[xX\*]*([0-9]{3,6})\b',
    re.IGNORECASE,
)

CATEGORY_RULES = [
    (re.compile(r'upi|phonepe|gpay|google pay|paytm|bhim', re.I), 'UPI'),
    (re.compile(r'fuel|petrol|diesel|hpcl|bpcl|iocl', re.I), 'Fuel'),
    (re.compile(r'swigg|zomato|restaurant|cafe|food', re.I), 'Food'),
    (re.compile(r'amazon|flipkart|myntra|ajio', re.I), 'Shopping'),
    (re.compile(r'electric|bescom|mse[bB]|water|gas bill', re.I), 'Utilities'),
    (re.compile(r'netflix|spotify|prime|hotstar|youtube', re.I), 'Subscriptions'),
    (re.compile(r'salary|payroll', re.I), 'Salary'),
    (re.compile(r'atm|cash wdl|withdrawal', re.I), 'Cash'),
    (re.compile(r'emi|loan', re.I), 'Loan'),
    (re.compile(r'interest|dividend', re.I), 'Interest'),
]


def _parse_amount(text: str) -> Optional[float]:
    m = AMOUNT_RE.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    if not raw:
        return None
    try:
        return float(raw.replace(',', ''))
    except ValueError:
        return None


def _direction(text: str) -> str:
    has_debit = bool(DEBIT_WORDS.search(text))
    has_credit = bool(CREDIT_WORDS.search(text))
    if has_debit and not has_credit:
        return 'expense'
    if has_credit and not has_debit:
        return 'income'
    if has_debit and has_credit:
        d = DEBIT_WORDS.search(text)
        c = CREDIT_WORDS.search(text)
        if d and c:
            return 'expense' if d.start() < c.start() else 'income'
    return 'expense'


def _merchant(text: str) -> Optional[str]:
    m = MERCHANT_RE.search(text)
    if not m:
        return None
    for g in m.groups():
        if g:
            name = g.strip(' .-_')
            name = re.split(
                r"\b(?:is successful|successful|has been|on \d|via|using|ref)\b",
                name,
                maxsplit=1,
                flags=re.I,
            )[0].strip(' .-_')
            if name.lower() in ('avl', 'bal', 'info', 'sms', 'a/c', 'ac', 'your'):
                continue
            if len(name) >= 2:
                return name[:80]
    return None


def _account_hint(text: str) -> Optional[str]:
    m = ACCOUNT_RE.search(text)
    return m.group(1) if m else None


def _category(text: str, merchant: Optional[str], tx_type: str) -> str:
    blob = f'{text} {merchant or ""}'
    for pattern, cat in CATEGORY_RULES:
        if pattern.search(blob):
            return cat
    return 'Income' if tx_type == 'income' else 'Expense'


def _description(merchant: Optional[str], tx_type: str, text: str) -> str:
    if merchant:
        prefix = 'Received from' if tx_type == 'income' else 'Paid to'
        return f'{prefix} {merchant}'[:200]
    clean = re.sub(r'\s+', ' ', text).strip()
    return (clean[:120] + ('\u2026' if len(clean) > 120 else ''))


def parse_sms(text: str, sender: str | None = None) -> Optional[ParsedSms]:
    if not text or not str(text).strip():
        return None
    text = str(text).strip()
    amount = _parse_amount(text)
    if amount is None or amount <= 0:
        return None
    tx_type = _direction(text)
    merchant = _merchant(text)
    account_hint = _account_hint(text)
    category = _category(text, merchant, tx_type)
    if sender and not merchant:
        if not re.match(r'^\+?[0-9]{8,}$', sender.strip()):
            merchant = sender.strip()[:40]
    desc = _description(merchant, tx_type, text)
    return ParsedSms(
        amount=round(amount, 2),
        tx_type=tx_type,
        description=desc,
        category=category,
        merchant=merchant,
        account_hint=account_hint,
        raw_matched=text[:300],
    )
