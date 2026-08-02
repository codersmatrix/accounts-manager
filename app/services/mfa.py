"""TOTP multi-factor authentication helpers."""
from __future__ import annotations

import io

import pyotp
import qrcode
from qrcode.image.svg import SvgPathImage


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


def qr_svg_markup(data: str, box_size: int = 6) -> str:
    """Generate an SVG QR code as an HTML-safe string (no external service)."""
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(image_factory=SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode('utf-8')
    if 'width=' not in svg[:80]:
        svg = svg.replace('<svg', '<svg width="200" height="200"', 1)
    return svg
