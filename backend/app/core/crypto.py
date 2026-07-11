"""Symmetric encryption for stored provider credentials (Fernet).

Per-user API keys are encrypted at rest (CLAUDE.md §15) — the DB only ever holds
ciphertext. The key comes from ``Settings.credentials_encryption_key``. A proper
urlsafe-base64 Fernet key is used as-is; any other passphrase is deterministically
stretched to a valid key (personal-use convenience), so the app runs without a
key-generation step while still supporting a real key in production.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class SecretDecryptionError(Exception):
    """Raised when a stored credential cannot be decrypted (wrong/rotated key)."""


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().credentials_encryption_key
    try:
        return Fernet(key)
    except (ValueError, TypeError):
        derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        return Fernet(derived)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise SecretDecryptionError() from exc


def mask_secret(plaintext: str) -> str:
    """Return a display-safe hint like ``****abcd`` (never the full secret)."""
    if len(plaintext) <= 4:
        return "****"
    return "****" + plaintext[-4:]
