"""Parse bank / UPI SMS text into transaction fields.

Handles common Indian bank patterns (HDFC, SBI, ICICI, Axis, PhonePe, GPay, etc.).
Category prefers merchant/purpose over payment rail (UPI).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ParsedSms:
    amount: float
    tx_type: str
    description: str
    category: str
    merchant: Optional[str] = None
    account_hint: Optional[str] = None
    raw_matched: Optional[str] = None

    def to_dict(self):
        return asdict(self)


AMOUNT_RE = re.compile(
    r'(?:(?:inr|rs\.?|\u20b9)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?))'
    r'|'
    r'([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*(?:inr|rs\.?|\u20b9)',
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
    (re.compile(r'\b(salary|payroll|stipend)\b', re.I), 'Salary'),
    (re.compile(r'\b(interest|dividend|int\.?\s*cr)\b', re.I), 'Interest'),
    (re.compile(r'\b(refund|cashback|cash back|reward)\b', re.I), 'Refund'),
    (re.compile(
        r'swiggy|zomato|dominos|domino\'?s|pizza|mcdonald|mcd|kfc|starbucks|'
        r'cafe|restaurant|dunzo|foodpanda|box8|faasos|behrouz|food\s*order',
        re.I,
    ), 'Food'),
    (re.compile(
        r'bigbasket|big basket|blinkit|zepto|instamart|jiomart|dmart|d-?mart|'
        r'reliance fresh|nature\'?s basket|grocery|groceries|supermarket',
        re.I,
    ), 'Groceries'),
    (re.compile(
        r'\b(fuel|petrol|diesel|hpcl|bpcl|iocl|indian oil|bharat petroleum|'
        r'hindustan petroleum|shell\s*petrol|reliance\s*petro)\b',
        re.I,
    ), 'Fuel'),
    (re.compile(
        r'\b(uber|ola|rapido|metro|irctc|railway|makemytrip|mmt|goibibo|'
        r'redbus|indigo|airindia|spicejet|vistara|fastag|toll|parking)\b',
        re.I,
    ), 'Transport'),
    (re.compile(
        r'amazon|flipkart|myntra|ajio|meesho|nykaa|tatacliq|snapdeal|'
        r'ikea|decathlon|croma|reliance digital',
        re.I,
    ), 'Shopping'),
    (re.compile(
        r'netflix|spotify|prime\s*video|amazon\s*prime|hotstar|disney|'
        r'youtube\s*premium|sony\s*liv|zee5|apple\s*music|icloud|'
        r'google\s*one|microsoft\s*365|subscription',
        re.I,
    ), 'Subscriptions'),
    (re.compile(
        r'\b(electric|electricity|bescom|mse[bs]|tata\s*power|adani\s*power|'
        r'water\s*bill|gas\s*bill|indane|bharatgas|broadband|'
        r'airtel|jio|vodafone|bsnl|postpaid|prepaid|recharge|bbps|bill\s*pay)\b',
        re.I,
    ), 'Utilities'),
    (re.compile(
        r'\b(pharmacy|apollo|1mg|pharmeasy|netmeds|hospital|clinic|'
        r'medicine|medical|diagnostic)\b',
        re.I,
    ), 'Health'),
    (re.compile(
        r'\b(school|college|tuition|udemy|coursera|byju|unacademy|education|fees)\b',
        re.I,
    ), 'Education'),
    (re.compile(r'\b(emi|loan\s*emi|loan\s*repay|nbfc)\b', re.I), 'Loan'),
    (re.compile(r'\b(atm|cash\s*wdl|cash\s*withdraw|withdrawal)\b', re.I), 'Cash'),
    (re.compile(
        r'\b(insurance|lic|policybazaar|mutual\s*fund|sip\b|groww|zerodha|upstox)\b',
        re.I,
    ), 'Investment'),
]

UPI_RAIL_RE = re.compile(
    r'\b(upi|phonepe|gpay|google\s*pay|paytm|bhim|bharatpe)\b', re.I
)


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
                r'\b(?:is successful|successful|has been|on \d|via|using|ref)\b',
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
    blobs = []
    if merchant:
        blobs.append(merchant)
    blobs.append(text or '')
    for blob in blobs:
        for pattern, cat in CATEGORY_RULES:
            if pattern.search(blob):
                return cat
    if tx_type == 'income':
        return 'Income'
    if UPI_RAIL_RE.search(text or '') or UPI_RAIL_RE.search(merchant or ''):
        return 'Transfer'
    return 'Expense'


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
            category = _category(text, merchant, tx_type)
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
