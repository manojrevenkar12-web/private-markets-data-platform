"""Builds the warehouse with dbt into a schema of its own (write), so tests and gates can run on it (audit)
before the serving views point at it (publish)."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .config import database_url, root, settings, today


@dataclass
class BuildResult:
    schema: str
    ok: bool
    models: int = 0
    tests: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)


def dbt_vars() -> dict[str, Any]:
    s = settings()
    return {
        "as_of": today().isoformat(),
        "statement_due_days": s["freshness"]["gp_statement_days"],
        "nav_move_threshold": s["gates"]["statement_unexplained_move"]["threshold"],
        "overdue_grace_days": s["reconciliation"]["overdue_grace_days"],
        "duplicate_window_days": s["reconciliation"]["duplicate_window_days"],
        "amount_tolerance": s["reconciliation"]["amount_tolerance_eur"],
        "unmatched_days": s["gates"]["unmatched_receipts"]["days"],
    }


def _db_env() -> dict[str, str]:
    u = urlparse(database_url().replace("postgresql+psycopg", "postgresql"))
    return {
        "PMD_DB_HOST": u.hostname or "localhost",
        "PMD_DB_PORT": str(u.port or 5432),
        "PMD_DB_USER": unquote(u.username or ""),
        "PMD_DB_PASSWORD": unquote(u.password or ""),
        "PMD_DB_NAME": (u.path or "/").lstrip("/"),
    }


@contextmanager
def _env(extra: dict[str, str]) -> Iterator[None]:
    old = {k: os.environ.get(k) for k in extra}
    os.environ.update(extra)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def project_dir() -> Path:
    return root() / "warehouse"


def dbt(args: list[str], schema: str) -> Any:
    from dbt.cli.main import dbtRunner

    proj = project_dir()
    with _env(
        {
            **_db_env(),
            "PMD_DBT_SCHEMA": schema,
            "DBT_LOG_PATH": str(proj / "logs"),
            "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        }
    ):
        return dbtRunner().invoke(
            [
                *args,
                "--project-dir",
                str(proj),
                "--profiles-dir",
                str(proj),
                "--vars",
                json.dumps(dbt_vars()),
                "--quiet",
            ]
        )


def build(schema: str) -> BuildResult:
    """dbt build (models and tests in dependency order) into `schema`."""
    res = dbt(["build"], schema)
    out = BuildResult(schema, bool(res.success))
    for r in getattr(res.result, "results", None) or []:
        node = r.node
        kind = node.resource_type
        status = str(r.status)
        if kind == "model":
            out.models += 1
        elif kind == "test":
            out.tests += 1
        if status in ("error", "fail") or (kind == "test" and status == "warn"):
            out.failures.append(
                {
                    "node": node.name,
                    "kind": str(kind),
                    "status": status,
                    "message": (r.message or "")[:300],
                    "failures": getattr(r, "failures", None),
                }
            )
    if res.exception is not None:
        out.ok = False
        out.failures.append({"node": "dbt", "kind": "run", "status": "error", "message": str(res.exception)[:500]})
    return out
