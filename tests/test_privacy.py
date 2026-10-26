from __future__ import annotations

from typing import Any

import pytest

from pmd import privacy


def test_keys_are_stable_and_depend_on_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    a = privacy.client_key("C-000123")
    assert a == privacy.client_key(" c-000123 ") and a.startswith("ck_") and len(a) == 19
    monkeypatch.setenv("PMD_PSEUDONYM_KEY", "another-secret")
    assert privacy.client_key("C-000123") != a


def test_remittance_loses_the_client_number_keeps_the_link() -> None:
    red, call, key = privacy.redact_remittance("PE5-2026Q4 C-000123")
    assert "C-000123" not in red and call == "PE5-2026Q4" and key == privacy.client_key("C-000123")
    assert privacy.redact_remittance("Kapitalabruf") == ("Kapitalabruf", None, None)


def test_iban_checksum() -> None:
    assert privacy.iban_valid("DE89 3704 0044 0532 0130 00")
    assert not privacy.iban_valid("DE89370400440532013001")


def test_age_band() -> None:
    assert privacy.age_band(1980, 2026) == "40-49"
    assert privacy.age_band(1940, 2026) == "80+"


def test_a_database_refuses_a_second_pseudonymisation_key(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from pmd import db

    db.bootstrap()  # the key it was loaded with: fine, and idempotent
    monkeypatch.setenv("PMD_PSEUDONYM_KEY", "a-different-secret")
    with pytest.raises(privacy.KeyChanged):
        db.bootstrap()
    stored = db.scalar("select fingerprint from ops.pseudonym_key")
    assert stored != privacy.key_fingerprint() and "a-different-secret" not in stored
