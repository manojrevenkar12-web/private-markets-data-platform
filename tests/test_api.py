from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

OPS = {"x-pmd-role": "operations", "x-pmd-actor": "anna.ops"}


@pytest.fixture()
def client(world: dict[str, Any]) -> TestClient:
    from pmd.api import app

    return TestClient(app)


def test_overview_and_lists(client: TestClient) -> None:
    o = client.get("/api/overview").json()
    assert len(o["feeders"]) == 3 and o["clients"]["clients"] > 0 and o["breaks"]
    for url in (
        "/api/runs",
        "/api/freshness",
        "/api/breaks",
        "/api/cash",
        "/api/funds",
        "/api/clients",
        "/api/lineage",
    ):
        assert client.get(url).status_code == 200, url


def test_bitemporal_fund_view(client: TestClient) -> None:
    f = client.get("/api/funds/KES4").json()
    restated = f["restatements"][0]
    before = client.get(f"/api/funds/KES4?known_at={restated['received_on']}").json()
    just_before = [
        v
        for v in client.get("/api/funds/KES4?known_at=" + _day_before(restated["received_on"])).json()["as_known"]
        if v["period_end"] == restated["period_end"]
    ]
    now = [v for v in before["as_known"] if v["period_end"] == restated["period_end"]]
    assert just_before[0]["version"] == 1 and now[0]["version"] == 2


def _day_before(d: str) -> str:
    import datetime as dt

    return (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()


def test_client_detail_has_no_personal_data(client: TestClient) -> None:
    key = client.get("/api/clients").json()["rows"][0]["client_key"]
    body = client.get(f"/api/clients/{key}").text
    assert "@example.com" not in body and '"iban"' not in body
    assert {"performance", "lookthrough", "payments"} <= set(client.get(f"/api/clients/{key}").json())


def test_reveal_needs_the_role_and_a_reason_and_is_logged(client: TestClient) -> None:
    from pmd import db

    key = client.get("/api/clients").json()["rows"][0]["client_key"]
    before = db.scalar("select count(*) from pii.reveal_log")
    assert client.post(f"/api/clients/{key}/reveal", json={"reason": "statement query"}).status_code == 403
    assert client.post(f"/api/clients/{key}/reveal", json={"reason": "x"}, headers=OPS).status_code == 422
    r = client.post(f"/api/clients/{key}/reveal", json={"reason": "client called about a capital call"}, headers=OPS)
    assert r.status_code == 200 and r.json()["client_id"].startswith("C-")
    log = db.rows("select actor, role, granted from pii.reveal_log order by id desc limit 2")
    assert db.scalar("select count(*) from pii.reveal_log") == before + 2
    assert log[0] == {"actor": "anna.ops", "role": "operations", "granted": True}
    assert log[1]["granted"] is False


def test_break_actions_need_a_team_role(client: TestClient) -> None:
    b = client.get("/api/breaks?kind=payment_over").json()[0]
    assert (
        client.post(
            f"/api/breaks/{b['break_id']}/actions", json={"action": "note", "note": "called the client"}
        ).status_code
        == 403
    )
    r = client.post(
        f"/api/breaks/{b['break_id']}/actions", json={"action": "note", "note": "called the client"}, headers=OPS
    )
    assert r.status_code == 200 and r.json()["last_note"] == "called the client" and r.json()["status"] == "open"
    bad = client.post(f"/api/breaks/{b['break_id']}/actions", json={"action": "delete", "note": "nope"}, headers=OPS)
    assert bad.status_code == 422 and bad.headers["content-type"].startswith("application/problem+json")


def test_release_is_fund_accounting_only(client: TestClient) -> None:
    fid = client.get("/api/freshness").json()["holds"][0]["file_id"]
    assert (
        client.post(f"/api/statements/{fid}/release", json={"note": "confirmed with GP"}, headers=OPS).status_code
        == 403
    )
    assert (
        client.post(
            "/api/statements/999999/release", json={"note": "confirmed"}, headers={"x-pmd-role": "fund_accounting"}
        ).status_code
        == 404
    )


def test_unknown_things_are_404_problems(client: TestClient) -> None:
    for url in (
        "/api/clients/ck_0000000000000000",
        "/api/clients/robert",
        "/api/funds/NOPE",
        "/api/runs/none",
        "/api/funds/drop table",
    ):
        r = client.get(url)
        assert r.status_code == 404, url


def test_tokens_when_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PMD_API_TOKENS", "s3cret:lea:fund_accounting")
    assert client.get("/api/overview").status_code == 401
    assert client.get("/api/overview", headers={"authorization": "Bearer s3cret"}).status_code == 200
