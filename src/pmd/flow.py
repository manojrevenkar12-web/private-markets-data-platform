"""The run, as one task graph. `pmd run` executes it in order; the Airflow DAG (dags/private_markets.py)
is generated from the same list, so the two can never disagree about what depends on what."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import db, ingest, publish, streaming, warehouse
from .config import today


@dataclass
class RunContext:
    run_id: str
    results: dict[str, Any] = field(default_factory=dict)

    @property
    def schema(self) -> str:
        return "build_" + re.sub(r"[^a-z0-9_]", "_", self.run_id.lower())[:50]


def new_run_id() -> str:
    return f"{today():%Y%m%d}_{dt.datetime.now():%H%M%S%f}"[:22]


def _build(ctx: RunContext) -> dict[str, Any]:
    res = warehouse.build(ctx.schema)
    ctx.results["build"] = res
    return {"ok": res.ok, "models": res.models, "tests": res.tests, "failures": res.failures}


def _gates(ctx: RunContext) -> dict[str, Any]:
    res = ctx.results.get("build")
    if res is None:  # a separate process (Airflow): read the build's outcome back from the schema
        ok = bool(
            db.scalar(
                "select count(*) from information_schema.tables where table_schema = :s and table_name = 'fct_client_positions'",
                s=ctx.schema,
            )
        )
        res = warehouse.BuildResult(ctx.schema, ok)
    gates = publish.gates(ctx.schema, res.ok, res.failures)
    ctx.results["gates"] = gates
    blocked = [g.name for g in gates if g.blocks]
    counts = {m: int(db.scalar(f"select count(*) from {ctx.schema}.{m}") or 0) for m in publish.MARTS} if res.ok else {}
    prev = publish.published_schema()
    diff = publish.diff(prev, ctx.schema) if res.ok and prev and prev != ctx.schema else None
    publish.record(ctx.run_id, ctx.schema, "blocked" if blocked else "audited", gates, counts, diff)
    return {"blocked": blocked, "gates": [g.__dict__ for g in gates]}


def _publish(ctx: RunContext) -> dict[str, Any]:
    status = db.scalar("select status from ops.runs where run_id = :r", r=ctx.run_id)
    if status != "audited":
        return {"published": False, "reason": f"run is {status}"}
    publish.publish(ctx.schema)
    db_status = "published"
    with db.begin() as c:
        c.exec_driver_sql(
            f"update ops.runs set status = '{db_status}', finished_at = now() where run_id = '{ctx.run_id}'"
        )
    return {"published": True, "schema": ctx.schema}


@dataclass
class Task:
    name: str
    fn: Callable[[RunContext], Any]
    upstream: list[str]
    doc: str


TASKS: list[Task] = [
    Task("bootstrap", lambda ctx: db.bootstrap(), [], "Landing schemas, roles and the reveal function"),
    Task("load_market", lambda ctx: ingest.load_market().as_dict(), ["bootstrap"], "EUR/USD reference rates"),
    Task(
        "load_ops",
        lambda ctx: ingest.load_ops().as_dict(),
        ["bootstrap"],
        "Fund master data, commitments, calls, distributions",
    ),
    Task(
        "load_crm",
        lambda ctx: ingest.load_crm().as_dict(),
        ["load_ops"],
        "Clients into the vault and pseudonymised; erasure requests",
    ),
    Task(
        "load_statements", lambda ctx: ingest.load_statements().as_dict(), ["load_ops"], "GP capital account statements"
    ),
    Task("load_bank", lambda ctx: ingest.load_bank().as_dict(), ["bootstrap"], "Custodian camt.053 statements"),
    Task(
        "consume_payments",
        lambda ctx: streaming.consume(),
        ["bootstrap"],
        "Instant payment notifications from the topic",
    ),
    Task(
        "build",
        _build,
        ["load_market", "load_crm", "load_statements", "load_bank", "consume_payments"],
        "dbt build into the run's own schema",
    ),
    Task("gates", _gates, ["build"], "Audit the build: tests, drift, reconciliation"),
    Task("publish", _publish, ["gates"], "Point the serving views at the audited build"),
    Task("cleanup", lambda ctx: publish.cleanup(), ["publish"], "Drop old builds"),
]


def order() -> list[Task]:
    done: list[Task] = []
    names: set[str] = set()
    pending = list(TASKS)
    while pending:
        ready = [t for t in pending if set(t.upstream) <= names]
        if not ready:
            raise ValueError("cycle in the task graph")
        for t in ready:
            done.append(t)
            names.add(t.name)
            pending.remove(t)
    return done


def run_task(name: str, run_id: str) -> Any:
    task = next(t for t in TASKS if t.name == name)
    return task.fn(RunContext(run_id))


def run(run_id: str | None = None) -> dict[str, Any]:
    ctx = RunContext(run_id or new_run_id())
    out: dict[str, Any] = {"run_id": ctx.run_id, "schema": ctx.schema, "tasks": {}}
    with db.engine().connect() as lock:
        # one run at a time
        lock.exec_driver_sql("select pg_advisory_lock(42002)")
        try:
            for t in order():
                out["tasks"][t.name] = t.fn(ctx)
        finally:
            lock.exec_driver_sql("select pg_advisory_unlock(42002)")
    return out
