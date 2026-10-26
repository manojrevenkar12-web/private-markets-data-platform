"""The whole platform on a small simulated world: load, build, audit, publish, and check it against truth."""

from __future__ import annotations

from typing import Any

from pmd import db
from pmd.evaluate import evaluate
from pmd.flow import run
from pmd.publish import published_schema


def test_first_run_publishes_with_only_warnings(world: dict[str, Any]) -> None:
    tasks = world["run"]["tasks"]
    assert tasks["publish"]["published"], tasks["gates"]
    gates = {g["name"]: g for g in tasks["gates"]["gates"]}
    assert gates["dbt_tests"]["passed"] and gates["marts_not_empty"]["passed"]
    assert not tasks["gates"]["blocked"]
    assert published_schema() == world["run"]["schema"]


def test_every_statement_reads_right_and_every_planted_problem_surfaces(world: dict[str, Any]) -> None:
    ev = evaluate(published_schema() or "")
    for field, r in ev["statements"]["fields"].items():
        assert r["right"] == r["of"], (field, ev["statements"]["wrong"])
    p = ev["planted"]
    assert p["found"]["right"] == p["found"]["of"], p["planted"]
    assert p["unexplained_breaks"] == 0, p["unexplained_examples"]
    assert ev["nav"]["reported_quarters"]["right"] == ev["nav"]["reported_quarters"]["of"]


def test_a_second_run_loads_nothing_twice_and_changes_nothing(world: dict[str, Any]) -> None:
    files = db.scalar("select count(*) from ops.files")
    entries = db.scalar("select count(*) from raw.bank_entries")
    second = run("test_second")
    assert second["tasks"]["publish"]["published"]
    assert db.scalar("select count(*) from ops.files") == files
    assert db.scalar("select count(*) from raw.bank_entries") == entries
    assert second["tasks"]["load_statements"]["loaded"] == 0
    diff = db.scalar("select diff from ops.runs where run_id = 'test_second'")
    # nothing moves, except breaks someone has acted on since (their last note and status)
    acted = db.scalar("select count(distinct break_id) from ops.break_actions")
    assert all(d["added"] == d["removed"] == d["changed"] == 0 for m, d in diff.items() if m != "recon_breaks"), diff
    assert diff["recon_breaks"]["added"] == diff["recon_breaks"]["removed"] == 0
    assert diff["recon_breaks"]["changed"] <= acted


def test_restatement_is_kept_as_a_second_version(world: dict[str, Any]) -> None:
    s = published_schema()
    rows = db.rows(
        f"select fund, period_end, version, known_from, known_until from {s}.int_statement_versions where versions > 1"
    )
    assert any(r["fund"] == "KES4" for r in rows)
    first = next(r for r in rows if r["version"] == 1)
    assert first["known_until"] is not None and first["known_until"] > first["known_from"]


def test_statement_in_thousands_is_held_and_its_quarter_estimated(world: dict[str, Any]) -> None:
    holds = db.rows("select fund, period_end, hold_reason from serving.statement_holds")
    assert [h["fund"] for h in holds] == ["ORI9"]
    q = db.rows(
        "select nav_source, estimate_reason from serving.fct_fund_nav where fund = 'ORI9' and quarter_end = :p",
        p=holds[0]["period_end"],
    )
    assert q == [{"nav_source": "estimated", "estimate_reason": "statement held"}]


def test_releasing_a_held_statement_takes_effect_on_the_next_run(world: dict[str, Any]) -> None:
    fid = db.scalar("select file_id from serving.statement_holds")
    with db.begin() as c:
        c.exec_driver_sql(
            "insert into ops.statement_releases (file_id, actor, note) values (%(f)s, 'test', 'checked with the GP')",
            {"f": fid},
        )
    try:
        out = run("test_release")
        # the released statement is in thousands, so the fund's NAV collapses with no new statement to explain
        # it: the drift gate stops the build and clients keep the last good numbers
        gates = {g["name"]: g for g in out["tasks"]["gates"]["gates"]}
        assert not out["tasks"]["publish"]["published"]
        assert not gates["nav_drift"]["passed"] and "ORI9" in gates["nav_drift"]["detail"]
        assert published_schema() != out["schema"]
        assert db.scalar(f"select count(*) from {out['schema']}.statement_holds") == 0
        # a second person can still publish it, on the record
        from pmd.publish import approve

        approve("test_release", "lea.fa", "GP confirmed the figures are in thousands; corrected statement requested")
        assert published_schema() == out["schema"]
        assert db.scalar("select approved_by from ops.runs where run_id = 'test_release'") == "lea.fa"
    finally:
        with db.begin() as c:
            c.exec_driver_sql("delete from ops.statement_releases where file_id = %(f)s", {"f": fid})
        # back to the held statement for the tests that follow: that moves the NAV back, so it is approved too
        back = run("test_after_release")
        if not back["tasks"]["publish"].get("published"):
            from pmd.publish import approve

            approve("test_after_release", "lea.fa", "statement held again")


def test_reconciliation_breaks_keep_their_decisions_across_runs(world: dict[str, Any]) -> None:
    bid = db.scalar(
        "select break_id from serving.recon_breaks where kind = 'payment_duplicate' order by break_id limit 1"
    )
    with db.begin() as c:
        c.exec_driver_sql(
            "insert into ops.break_actions (break_id, action, note, actor) values (%(b)s, 'resolve', 'refunded', 'test')",
            {"b": bid},
        )
    out = run("test_resolve")
    assert out["tasks"]["publish"]["published"]
    assert db.scalar("select status from serving.recon_breaks where break_id = :b", b=bid) == "resolved"


def test_erasure_deletes_a_prospect_and_holds_an_investor(world: dict[str, Any]) -> None:
    rows = {r["status"]: r for r in db.rows("select * from ops.erasure_requests")}
    assert set(rows) == {"erased", "retention_hold"}
    gone = rows["erased"]["client_key"]
    assert db.scalar("select count(*) from pii.client_vault where client_key = :k", k=gone) == 0
    assert db.scalar("select count(*) from raw.clients where client_key = :k", k=gone) == 0
    held = rows["retention_hold"]["client_key"]
    assert db.scalar("select count(*) from pii.client_vault where client_key = :k", k=held) == 1


def test_no_personal_data_outside_the_vault(world: dict[str, Any]) -> None:
    """Every text column of every table outside pii, scanned for every name, e-mail and IBAN in the vault."""
    vault = db.rows("select first_name || ' ' || last_name as name, email, iban from pii.client_vault")
    needles = {v["email"] for v in vault} | {v["iban"] for v in vault} | {v["name"] for v in vault}
    cols = db.rows(
        """select table_schema, table_name, column_name from information_schema.columns
           where table_schema not in ('pii', 'pg_catalog', 'information_schema')
             and data_type in ('text', 'character varying')"""
    )
    leaks = []
    for c in cols:
        vals = db.rows(
            f'select distinct "{c["column_name"]}" as v from {c["table_schema"]}."{c["table_name"]}" limit 20000'
        )
        hits = [r["v"] for r in vals if r["v"] in needles]
        if hits:
            leaks.append((c["table_schema"], c["table_name"], c["column_name"], hits[:2]))
    assert leaks == []


def test_feeder_nav_is_the_sum_of_its_clients(world: dict[str, Any]) -> None:
    rows = db.rows(
        """select f.feeder, f.quarter_end, f.nav_eur, sum(p.nav_eur) as clients
           from serving.fct_feeder_nav f join serving.fct_client_positions p using (feeder, quarter_end)
           group by 1, 2, 3"""
    )
    assert rows and all(abs(r["nav_eur"] - r["clients"]) < 1 for r in rows)


def test_xirr_matches_an_independent_calculation(world: dict[str, Any]) -> None:
    import datetime as dt
    import random

    rnd = random.Random(3)
    for _ in range(25):
        d0 = dt.date(2023, 1, 1)
        dates = sorted(d0 + dt.timedelta(days=rnd.randint(0, 1200)) for _ in range(5))
        amounts = [-rnd.uniform(1000, 5000) for _ in range(4)] + [rnd.uniform(5000, 30000)]

        def npv(r: float, dates: list = dates, amounts: list = amounts) -> float:  # type: ignore[type-arg]
            return sum(a / (1 + r) ** ((d - dates[0]).days / 365) for d, a in zip(dates, amounts, strict=True))

        lo, hi = -0.99, 10.0
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if npv(mid) > 0 else (lo, mid)
        got = db.scalar(
            "select pmd_util.xirr(cast(:d as date[]), cast(:a as numeric[]))",
            d="{" + ",".join(x.isoformat() for x in dates) + "}",
            a="{" + ",".join(f"{x:.2f}" for x in amounts) + "}",
        )
        assert got is not None and abs(float(got) - mid) < 1e-3
