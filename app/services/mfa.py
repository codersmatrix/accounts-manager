"""TOTP multi-factor authentication helpers."""
from __future__ import annotations

import pyotp


ISSUER = 'Accounts Manager'


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, username: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=ISSUER)


def verify_code(secret: str | None, code: str | None) -> bool:
    if not secret or not code:
        return False
    code = ''.join(c for c in str(code).strip() if c.isdigit())
    if len(code) != 6:
        return False
    try:
        totp = pyotp.TOTP(secret)
        return bool(totp.verify(code, valid_window=1))
    except Exception:
        return False
