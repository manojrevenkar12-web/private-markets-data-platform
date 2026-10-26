"""Write, audit, publish.

Every run builds the warehouse into a schema of its own (build_<run id>). The gates below run on that build.
Only if none of them blocks do the views in the serving schema - the only thing the API, dashboards and
analysts read - switch to the new build, all in one transaction. A blocked build stays where it is for a
person to look at; clients keep seeing the last good numbers.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from . import db
from .config import settings, today

# What the serving schema exposes, and the key each mart is diffed on.
MARTS: dict[str, list[str]] = {
    "fct_payment_status": ["expected_id"],
    "fct_fund_nav": ["fund", "quarter_end"],
    "fct_feeder_nav": ["feeder", "quarter_end"],
    "fct_client_positions": ["client_key", "feeder", "quarter_end"],
    "fct_client_lookthrough": ["client_key", "feeder", "fund"],
    "client_performance": ["client_key", "feeder"],
    "recon_breaks": ["break_id"],
    "nav_restatements": ["fund", "period_end", "version"],
    "statement_holds": ["file_id"],
    "dim_clients": ["client_key"],
    "cash_now": ["call_id"],
    "data_freshness": ["source", "feed"],
}


@dataclass
class Gate:
    name: str
    severity: str  # block | warn
    passed: bool
    detail: str
    count: int = 0

    @property
    def blocks(self) -> bool:
        return not self.passed and self.severity == "block"


def published_schema() -> str | None:
    return db.scalar("select build_schema from ops.runs where status = 'published' order by finished_at desc limit 1")


def _count(schema: str, table: str, where: str = "true") -> int:
    return int(db.scalar(f"select count(*) from {schema}.{table} where {where}") or 0)


def gates(schema: str, build_ok: bool, build_failures: list[dict[str, Any]]) -> list[Gate]:
    cfg = settings()["gates"]
    out = [
        Gate(
            "dbt_tests",
            cfg["dbt_tests"]["severity"],
            build_ok,
            "every model built and every test passed"
            if build_ok
            else "; ".join(f"{f['node']}: {f['message'][:120]}" for f in build_failures[:5]),
            len(build_failures),
        )
    ]
    empty = [
        m
        for m in ("fct_client_positions", "fct_fund_nav", "fct_payment_status", "dim_clients")
        if build_ok and _count(schema, m) == 0
    ]
    out.append(
        Gate(
            "marts_not_empty",
            "block",
            not empty,
            "empty: " + ", ".join(empty) if empty else "every client-facing mart has rows",
            len(empty),
        )
    )
    if not build_ok:
        return out

    # client NAV drift against what clients see now, unless new statements explain it
    prev = published_schema()
    if prev and prev != schema:
        threshold = cfg["client_nav_drift"]["threshold"]
        last = db.scalar("select as_of from ops.runs where build_schema = :s", s=prev)
        rows = db.rows(
            f"""select n.feeder, n.quarter_end, n.nav_eur as new_nav, o.nav_eur as old_nav,
                   (select count(*) from {schema}.int_statement_versions v join {schema}.stg_target_funds t using (fund)
                     where t.feeder = n.feeder and v.received_on > :last) as new_statements
                from {schema}.fct_feeder_nav n join {prev}.fct_feeder_nav o using (feeder, quarter_end)
                where o.nav_eur <> 0 and abs(n.nav_eur - o.nav_eur) / abs(o.nav_eur) > :t""",
            last=last or dt.date.min,
            t=threshold,
        )
        unexplained = [r for r in rows if not r["new_statements"]]
        out.append(
            Gate(
                "client_nav_drift",
                cfg["client_nav_drift"]["severity"],
                not unexplained,
                f"no feeder NAV moved more than {threshold:.0%} without a new statement"
                if not unexplained
                else "; ".join(
                    f"{r['feeder']} {r['quarter_end']}: {r['old_nav']} -> {r['new_nav']}" for r in unexplained[:5]
                ),
                len(unexplained),
            )
        )

    days = cfg["unmatched_receipts"]["days"]
    n = _count(schema, "recon_breaks", f"kind = 'unmatched_receipt' and status = 'open' and age_days > {int(days)}")
    out.append(
        Gate(
            "unmatched_receipts",
            cfg["unmatched_receipts"]["severity"],
            n == 0,
            f"{n} receipts nobody has placed for more than {days} days",
            n,
        )
    )
    n = _count(schema, "recon_breaks", "kind = 'payment_overdue' and status = 'open'")
    out.append(Gate("overdue_calls", cfg["overdue_calls"]["severity"], n == 0, f"{n} capital call payments overdue", n))
    n = _count(schema, "recon_breaks", "kind = 'statement_late' and status = 'open'")
    out.append(
        Gate(
            "late_statements",
            cfg["late_statements"]["severity"],
            n == 0,
            f"{n} statements past due; their NAV is estimated",
            n,
        )
    )
    n = _count(schema, "statement_holds")
    out.append(
        Gate(
            "statement_holds",
            "warn",
            n == 0,
            f"{n} statements held back by their checks; their quarter is estimated",
            n,
        )
    )
    return out


def publish(schema: str) -> None:
    """Points every serving view at `schema` in one transaction."""
    with db.begin() as c:
        c.exec_driver_sql("select pg_advisory_xact_lock(42001)")
        for mart in MARTS:
            c.exec_driver_sql(f"drop view if exists serving.{mart}")
            c.exec_driver_sql(f"create view serving.{mart} as select * from {schema}.{mart}")
        c.exec_driver_sql("grant usage on schema serving to pmd_analyst, pmd_operations")
        c.exec_driver_sql(f"grant usage on schema {schema} to pmd_analyst, pmd_operations")
        c.exec_driver_sql(f"grant select on all tables in schema {schema} to pmd_analyst, pmd_operations")
        c.exec_driver_sql("grant select on all tables in schema serving to pmd_analyst, pmd_operations")


def cleanup(keep: int | None = None) -> list[str]:
    """Drops old build schemas, keeping the published one and the newest `keep` builds."""
    keep = keep or settings()["publish"]["keep_builds"]
    live = published_schema()
    builds = [r["build_schema"] for r in db.rows("select build_schema from ops.runs order by started_at desc")]
    existing = {
        r["schema_name"]
        for r in db.rows("select schema_name from information_schema.schemata where schema_name like 'build\\_%'")
    }
    keepers = set(builds[:keep]) | ({live} if live else set())
    dropped = []
    with db.begin() as c:
        for s in sorted(existing - keepers):
            c.exec_driver_sql(f"drop schema {s} cascade")
            dropped.append(s)
    return dropped


def diff(old: str, new: str) -> dict[str, Any]:
    """What changed between two builds, mart by mart: rows added, removed and changed, and the change in every
    numeric column's total. The record a reviewer reads before trusting a change to the models."""
    out: dict[str, Any] = {}
    for mart, keys in MARTS.items():
        k = ", ".join(keys)
        try:
            cols = db.rows(
                "select column_name, data_type from information_schema.columns where table_schema = :s and table_name = :t order by ordinal_position",
                s=new,
                t=mart,
            )
            old_cols = {
                r["column_name"]
                for r in db.rows(
                    "select column_name from information_schema.columns where table_schema = :s and table_name = :t",
                    s=old,
                    t=mart,
                )
            }
        except Exception:  # pragma: no cover
            continue
        if not cols or not old_cols:
            out[mart] = {"status": "missing in one build"}
            continue
        shared = [c["column_name"] for c in cols if c["column_name"] in old_cols]
        numeric = [
            c["column_name"]
            for c in cols
            if c["data_type"] in ("numeric", "integer", "bigint", "double precision")
            and c["column_name"] in old_cols
            and c["column_name"] not in keys
        ]
        on = " and ".join(f"n.{x} is not distinct from o.{x}" for x in keys)
        added = db.scalar(
            f"select count(*) from {new}.{mart} n where not exists (select 1 from {old}.{mart} o where {on})"
        )
        removed = db.scalar(
            f"select count(*) from {old}.{mart} o where not exists (select 1 from {new}.{mart} n where {on})"
        )
        cmp = " or ".join(f"n.{x} is distinct from o.{x}" for x in shared if x not in keys) or "false"
        changed = db.scalar(f"select count(*) from {new}.{mart} n join {old}.{mart} o on {on} where {cmp}")
        sums = {}
        for col in numeric:
            a = db.scalar(f"select coalesce(sum({col}), 0) from {old}.{mart}")
            b = db.scalar(f"select coalesce(sum({col}), 0) from {new}.{mart}")
            if a != b:
                sums[col] = {"old": _num(a), "new": _num(b)}
        out[mart] = {
            "rows_old": db.scalar(f"select count(*) from {old}.{mart}"),
            "rows_new": db.scalar(f"select count(*) from {new}.{mart}"),
            "added": added,
            "removed": removed,
            "changed": changed,
            "columns_added": sorted({c["column_name"] for c in cols} - old_cols),
            "columns_removed": sorted(old_cols - {c["column_name"] for c in cols}),
            "totals_changed": sums,
        }
    return out


def _num(x: Any) -> Any:
    return float(x) if isinstance(x, Decimal) else x


def record(
    run_id: str, schema: str, status: str, gate_list: list[Gate], counts: dict[str, int], diff_: dict[str, Any] | None
) -> None:
    with db.begin() as c:
        c.execute(
            text(
                """insert into ops.runs (run_id, build_schema, status, as_of, gates, counts, diff, finished_at)
                   values (:r, :s, :st, :a, cast(:g as jsonb), cast(:c as jsonb), cast(:d as jsonb), now())
                   on conflict (run_id) do update set status = excluded.status, gates = excluded.gates,
                   counts = excluded.counts, diff = excluded.diff, finished_at = now()"""
            ),
            {
                "r": run_id,
                "s": schema,
                "st": status,
                "a": today(),
                "g": json.dumps([asdict(g) for g in gate_list]),
                "c": json.dumps(counts),
                "d": json.dumps(diff_, default=str) if diff_ is not None else None,
            },
        )
