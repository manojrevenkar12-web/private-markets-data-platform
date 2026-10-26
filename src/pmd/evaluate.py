"""Checks the platform against what really happened in the simulated world. The only module that reads
data/truth: models, loaders, gates and the API never do (tests/test_isolation.py).

It answers: did every statement read right, did every planted problem surface as the right break, and did
anything surface that was not planted?
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import db
from .config import data_dir, settings, today
from .privacy import client_key

PAYMENT_BREAK = {
    "short": "payment_short",
    "over": "payment_over",
    "duplicate": "payment_duplicate",
    "unpaid": "payment_overdue",
}
MATCHED_ANYWAY = {
    "no_reference": ("paid", "paid_late"),
    "wrong_reference": ("paid", "paid_late"),
    "late": ("paid_late",),
}


def _truth(base: Path | None) -> dict[str, Any]:
    t = (base or data_dir()) / "truth"
    return {
        "world": json.loads((t / "world.json").read_text(encoding="utf-8")),
        "statements": json.loads((t / "statements.json").read_text(encoding="utf-8")),
    }


def _ratio(k: int, n: int) -> dict[str, Any]:
    return {"right": k, "of": n, "rate": round(k / n, 4) if n else None}


def statements(schema: str, base: Path | None = None) -> dict[str, Any]:
    truth = {(r["fund"], r["period_end"]): r for r in _truth(base)["statements"]}
    loaded = db.rows(
        f"""select c.fund, c.period_end, c.currency, c.commitment, c.paid_in, c.distributed, c.nav, c.unit_scale
            from {schema}.int_statement_checks c where not c.held and c.version = c.versions"""
    )
    fields = Counter()
    right = Counter()
    wrong: list[dict[str, Any]] = []
    for r in loaded:
        t = truth.get((r["fund"], r["period_end"].isoformat()))
        if t is None:
            wrong.append({"fund": r["fund"], "period_end": str(r["period_end"]), "why": "no such statement"})
            continue
        # a statement in thousands with three decimals is exact to half a euro, not to the cent
        scale = int(r["unit_scale"])
        tol = Decimal("0.5") * scale / 1000 + Decimal("0.005") if scale >= 1000 else Decimal("0.005")
        for f in ("commitment", "paid_in", "distributed", "nav"):
            fields[f] += 1
            if abs(Decimal(t[f]) - r[f]) <= tol:
                right[f] += 1
            else:
                wrong.append(
                    {
                        "fund": r["fund"],
                        "period_end": str(r["period_end"]),
                        "field": f,
                        "got": str(r[f]),
                        "expected": t[f],
                    }
                )
        fields["currency"] += 1
        right["currency"] += t["currency"] == r["currency"]
    delivered = sum(1 for t in truth.values() if t["delivered"])
    return {
        "delivered": delivered,
        "loaded_latest": len(loaded),
        "fields": {f: _ratio(right[f], n) for f, n in fields.items()},
        "wrong": wrong[:20],
    }


def planted(schema: str, base: Path | None = None) -> dict[str, Any]:
    w = _truth(base)["world"]
    breaks = db.rows(f"select kind, client_key, reference, fund from {schema}.recon_breaks")
    status = {
        (r["call_id"], r["client_key"]): r["status"]
        for r in db.rows(f"select call_id, client_key, status from {schema}.fct_payment_status")
    }
    by_kind: dict[str, Counter[str]] = {}
    expected_breaks: set[tuple[str, str, str]] = set()

    def tally(kind: str, ok: bool) -> None:
        by_kind.setdefault(kind, Counter())["found" if ok else "missed"] += 1

    due = {
        r["call_id"]: r["due_date"]
        for r in db.rows(f"select distinct call_id, due_date from {schema}.fct_payment_status")
    }
    grace = settings()["reconciliation"]["overdue_grace_days"]
    for p in w["planted"]:
        k = p["kind"]
        # money paid wrongly shows at once; money not paid yet only after the due date and the grace period
        open_call = "call" in p and p["call"] in due and due[p["call"]] + dt.timedelta(days=grace) >= today()
        if open_call and k in ("short", "unpaid", "no_reference", "wrong_reference", "late"):
            by_kind.setdefault(k, Counter())["not_due_yet"] += 1  # the call is still open: nothing to find yet
            continue
        if k in PAYMENT_BREAK:
            key = (PAYMENT_BREAK[k], client_key(p["client"]), p["call"])
            expected_breaks.add(key)
            tally(k, any((b["kind"], b["client_key"], b["reference"]) == key for b in breaks))
        elif k in MATCHED_ANYWAY:
            tally(k, status.get((p["call"], client_key(p["client"]))) in MATCHED_ANYWAY[k])
        elif k == "unknown_payer":
            key = ("unmatched_receipt", "", p["payment"])
            expected_breaks.add(key)
            tally(k, any(b["kind"] == "unmatched_receipt" and b["reference"] == p["payment"] for b in breaks))
        elif k == "statement_late":
            expected_breaks.add(("statement_late", p["fund"], p["period_end"]))
            tally(
                k,
                any(
                    b["kind"] == "statement_late" and b["fund"] == p["fund"] and b["reference"] == p["period_end"]
                    for b in breaks
                ),
            )
        elif k == "thousands_unlabelled":
            expected_breaks.add(("statement_held", p["fund"], ""))
            tally(k, any(b["kind"] == "statement_held" and b["fund"] == p["fund"] for b in breaks))
        elif k == "restated":
            tally(
                k,
                bool(
                    db.rows(
                        f"select 1 from {schema}.nav_restatements where fund = :f and period_end = :p",
                        f=p["fund"],
                        p=p["period_end"],
                    )
                ),
            )
        elif k == "duplicate_file":
            tally(
                k,
                (
                    db.scalar(
                        "select count(*) from ops.file_names n join ops.files f using (sha256) where n.path <> f.path"
                    )
                    or 0
                )
                > 0,
            )
        elif k == "scan_resent":
            tally(k, (db.scalar("select count(*) from ops.quarantine where rule = 'no_text_layer'") or 0) > 0)
        elif k == "erasure_prospect":
            tally(
                k,
                db.scalar("select count(*) from pii.client_vault where client_key = :k", k=client_key(p["client"]))
                == 0,
            )
        elif k == "erasure_on_hold":
            tally(
                k,
                db.scalar("select status from ops.erasure_requests where client_key = :k", k=client_key(p["client"]))
                == "retention_hold",
            )

    # breaks nothing planted explains
    unexplained = []
    for b in breaks:
        if b["kind"].startswith("payment_"):
            if (b["kind"], b["client_key"], b["reference"]) not in expected_breaks:
                unexplained.append(b)
        elif b["kind"] == "unmatched_receipt":
            if ("unmatched_receipt", "", b["reference"]) not in expected_breaks:
                unexplained.append(b)
        elif b["kind"] == "statement_late":
            if ("statement_late", b["fund"], b["reference"]) not in expected_breaks:
                unexplained.append(b)
        elif b["kind"] == "statement_held":
            if ("statement_held", b["fund"], "") not in expected_breaks:
                unexplained.append(b)
        else:
            unexplained.append(b)
    found = sum(c["found"] for c in by_kind.values())
    total = sum(c["found"] + c["missed"] for c in by_kind.values())
    return {
        "planted": {k: dict(v) for k, v in sorted(by_kind.items())},
        "found": _ratio(found, total),
        "breaks": len(breaks),
        "unexplained_breaks": len(unexplained),
        "unexplained_examples": [{k: str(v) for k, v in b.items()} for b in unexplained[:10]],
    }


def nav(schema: str, base: Path | None = None) -> dict[str, Any]:
    truth = {(r["fund"], r["period_end"]): Decimal(r["nav_eur"]) for r in _truth(base)["world"]["target_nav_eur"]}
    rows = db.rows(f"select fund, quarter_end, nav_eur from {schema}.fct_fund_nav where nav_source = 'statement'")
    ok = 0
    for r in rows:
        t = truth.get((r["fund"], r["quarter_end"].isoformat()))
        ok += t is not None and abs(t - r["nav_eur"]) <= max(Decimal("1"), t * Decimal("0.00001"))
    est = db.rows(f"select fund, quarter_end, nav_eur from {schema}.fct_fund_nav where nav_source = 'estimated'")
    errors = []
    for r in est:
        t = truth.get((r["fund"], r["quarter_end"].isoformat()))
        if t:
            errors.append(float(abs(r["nav_eur"] - t) / t))
    return {
        "reported_quarters": _ratio(ok, len(rows)),
        "estimated_quarters": len(est),
        "estimate_error_median": round(sorted(errors)[len(errors) // 2], 4) if errors else None,
    }


def evaluate(schema: str, base: Path | None = None) -> dict[str, Any]:
    return {"statements": statements(schema, base), "planted": planted(schema, base), "nav": nav(schema, base)}
