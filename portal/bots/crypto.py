"""Symmetric encryption for broker API credentials at rest (Fernet, key derived from the Django SECRET_KEY
or, preferably, a dedicated CREDENTIALS_KEY in .env). Secrets are only ever decrypted server-side for the trading engine."""
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    raw = os.getenv("CREDENTIALS_KEY") or settings.SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


def mask(value: str) -> str:
    return (value[:4] + "…" + value[-4:]) if value and len(value) > 10 else ("•" * len(value) if value else "")
