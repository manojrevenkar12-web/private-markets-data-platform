"""Personal data stays in the pii schema. Everything else carries keyed hashes: a client key for the client,
a counterparty key for an IBAN. Without the key (PMD_PSEUDONYM_KEY) the hashes cannot be linked back.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import warnings

DEV_KEY = "pmd-development-key-not-for-production"
CLIENT_ID = re.compile(r"\bC-\d{6}\b")
CALL_ID = re.compile(r"\b([A-Z]{2}\d-\d{4}Q[1-4])\b")


def _key() -> bytes:
    key = os.environ.get("PMD_PSEUDONYM_KEY")
    if not key:
        warnings.warn("PMD_PSEUDONYM_KEY is not set: using the development key", stacklevel=3)
        key = DEV_KEY
    return key.encode()


def _h(prefix: str, value: str) -> str:
    return prefix + hmac.new(_key(), value.encode(), hashlib.sha256).hexdigest()[:16]


def key_fingerprint() -> str:
    """Identifies the pseudonymisation key without revealing it."""
    return hmac.new(_key(), b"pmd-key-fingerprint", hashlib.sha256).hexdigest()[:16]


class KeyChanged(RuntimeError):
    """The database holds keys made with another pseudonymisation key."""


def client_key(client_id: str) -> str:
    return _h("ck_", client_id.strip().upper())


def counterparty_key(iban: str) -> str:
    return _h("cp_", re.sub(r"\s+", "", iban).upper())


def redact_remittance(text: str) -> tuple[str, str | None, str | None]:
    """Remittance text with client numbers replaced by client keys, plus the call and client it names."""
    call = CALL_ID.search(text or "")
    client = CLIENT_ID.search(text or "")
    key = client_key(client.group(0)) if client else None
    redacted = CLIENT_ID.sub(lambda m: client_key(m.group(0)), text or "")
    return redacted, call.group(1) if call else None, key


def iban_valid(iban: str) -> bool:
    s = re.sub(r"\s+", "", iban).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    moved = s[4:] + s[:4]
    digits = "".join(str(int(ch, 36)) for ch in moved)
    return int(digits) % 97 == 1


def age_band(birth_year: int, year: int) -> str:
    age = year - birth_year
    lo = max(20, min(80, age // 10 * 10))
    return f"{lo}-{lo + 9}" if lo < 80 else "80+"
