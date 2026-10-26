"""HTTP API for the console. It reads only the serving views (the last audited build) and operations' own
records; personal data is reachable through one endpoint, for the operations role, with a reason, logged.

Auth: PMD_API_TOKENS="token:actor:role,..." maps bearer tokens to people and roles. Without it (development)
the role comes from the x-pmd-role header and the actor from x-pmd-actor.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text

from . import db
from .config import root, settings, today
from .publish import published_schema

KEY = re.compile(r"^ck_[0-9a-f]{16}$")
FUND = re.compile(r"^[A-Z0-9]{3,6}$")
BREAK = re.compile(r"^[0-9a-f]{32}$")


class Caller(BaseModel):
    actor: str
    role: str


def caller(request: Request) -> Caller:
    tokens = os.environ.get("PMD_API_TOKENS", "")
    if tokens:
        auth = request.headers.get("authorization", "")
        for entry in tokens.split(","):
            tok, actor, role = [*entry.split(":"), "", ""][:3]
            if tok and auth == f"Bearer {tok}":
                return Caller(actor=actor, role=role)
        raise HTTPException(401, "a valid bearer token is required")
    return Caller(
        actor=request.headers.get("x-pmd-actor", "developer"), role=request.headers.get("x-pmd-role", "analyst")
    )


Who = Annotated[Caller, Depends(caller)]

app = FastAPI(title="private-markets-data-platform", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("PMD_CORS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def problem(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        {"title": exc.detail, "status": exc.status_code},
        status_code=exc.status_code,
        media_type="application/problem+json",
    )


@app.exception_handler(RequestValidationError)
async def invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(x) for x in first.get("loc", ()) if x != "body")
    return JSONResponse(
        {"title": "the request is not valid", "detail": f"{where}: {first.get('msg', 'invalid')}", "status": 422},
        status_code=422,
        media_type="application/problem+json",
    )


def _served() -> str:
    s = published_schema()
    if not s:
        raise HTTPException(503, "nothing is published yet: run `pmd run`")
    return s


def _rows(sql: str, **params: Any) -> list[dict[str, Any]]:
    return db.rows(sql, **params)


# --------------------------------------------------------------------------- runs and health


@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        live = published_schema()
    except Exception as e:  # pragma: no cover - database down
        raise HTTPException(503, f"database unavailable: {type(e).__name__}") from e
    return {"status": "ok", "published": live, "as_of": today().isoformat()}


@app.get("/api/overview")
def overview(_: Who) -> dict[str, Any]:
    _served()
    run = _rows(
        "select run_id, status, as_of, finished_at, gates from ops.runs where status = 'published' order by finished_at desc limit 1"
    )[0]
    latest = _rows("select * from ops.runs order by started_at desc limit 1")[0]
    feeders = _rows(
        """select f.feeder, f.feeder_name, f.quarter_end, f.nav_eur, f.cash_eur, f.total_commitment, f.has_estimates
           from serving.fct_feeder_nav f
           join (select feeder, max(quarter_end) q from serving.fct_feeder_nav group by feeder) l
             on l.feeder = f.feeder and l.q = f.quarter_end order by f.feeder"""
    )
    breaks = _rows(
        """select kind, owner, count(*) as open, coalesce(sum(abs(difference_eur)), 0) as amount_eur
           from serving.recon_breaks b
           where coalesce((select a.action from ops.break_actions a where a.break_id = b.break_id order by a.at desc, a.id desc limit 1), 'open') <> 'resolve'
           group by kind, owner order by open desc"""
    )
    fresh = _rows(
        "select source, status, count(*) as feeds from serving.data_freshness group by source, status order by source, status"
    )
    return {
        "as_of": run["as_of"],
        "published_run": run,
        "latest_run": {k: latest[k] for k in ("run_id", "status", "started_at", "finished_at", "gates")},
        "feeders": feeders,
        "clients": _rows(
            "select count(*) as clients, coalesce(sum(total_commitment), 0) as commitments from serving.dim_clients where total_commitment > 0"
        )[0],
        "breaks": breaks,
        "freshness": fresh,
        "cash_now": _rows("select * from serving.cash_now order by due_date, call_id"),
    }


@app.get("/api/runs")
def runs(_: Who, limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    return _rows(
        "select run_id, status, build_schema, as_of, started_at, finished_at, gates, counts from ops.runs order by started_at desc limit :n",
        n=limit,
    )


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str, _: Who) -> dict[str, Any]:
    rows = _rows("select * from ops.runs where run_id = :r", r=run_id)
    if not rows:
        raise HTTPException(404, f"no run {run_id}")
    return rows[0]


@app.get("/api/freshness")
def freshness(_: Who) -> dict[str, Any]:
    _served()
    return {
        "feeds": _rows("select * from serving.data_freshness order by source, status desc, feed"),
        "quarantine": _rows(
            """select q.file_id, f.source, f.path, f.received_on, q.rule, q.detail, q.at
               from ops.quarantine q join ops.files f using (file_id) order by q.at desc"""
        ),
        "duplicates": _rows(
            """select n.path, f.path as same_as, f.file_id, n.seen_at
               from ops.file_names n join ops.files f using (sha256) where n.path <> f.path order by n.seen_at desc"""
        ),
        "dead_events": _rows("select event_id, rule, detail, at from ops.dead_events order by at desc limit 50"),
        "holds": _rows("select * from serving.statement_holds order by received_on desc"),
        "erasures": _rows(
            "select request_id, client_key, requested_on, status, reason, decided_at from ops.erasure_requests order by requested_on desc"
        ),
    }


# --------------------------------------------------------------------------- reconciliation


BREAK_COLUMNS = """b.break_id, b.kind, b.owner, b.feeder, b.fund, b.client_key, b.reference, b.expected_eur,
  b.actual_eur, b.difference_eur, b.opened_on, b.age_days, b.detail"""


def _break_rows(where: str, **params: Any) -> list[dict[str, Any]]:
    return _rows(
        f"""select {BREAK_COLUMNS},
              coalesce(a.action, 'open') as last_action, a.note as last_note, a.actor as last_actor, a.at as last_action_at,
              case when a.action = 'resolve' then 'resolved' else 'open' end as status
            from serving.recon_breaks b
            left join lateral (
              select action, note, actor, at from ops.break_actions x where x.break_id = b.break_id
              order by at desc, id desc limit 1) a on true
            where {where}
            order by (a.action = 'resolve') nulls first, b.age_days desc, abs(coalesce(b.difference_eur, 0)) desc""",
        **params,
    )


@app.get("/api/breaks")
def breaks(
    _: Who,
    kind: str | None = Query(None, pattern=r"^[a-z_]{3,40}$"),
    owner: str | None = Query(None, pattern=r"^(operations|fund_accounting)$"),
    status: str = Query("open", pattern=r"^(open|resolved|all)$"),
) -> list[dict[str, Any]]:
    _served()
    rows = _break_rows(
        "(cast(:k as text) is null or b.kind = :k) and (cast(:o as text) is null or b.owner = :o)", k=kind, o=owner
    )
    return rows if status == "all" else [r for r in rows if r["status"] == status]


class BreakAction(BaseModel):
    action: str = Field(pattern=r"^(resolve|reopen|note)$")
    note: str = Field(min_length=3, max_length=2000)


@app.post("/api/breaks/{break_id}/actions")
def act(break_id: str, body: BreakAction, who: Who) -> dict[str, Any]:
    if not BREAK.match(break_id):
        raise HTTPException(404, "no such break")
    _served()
    if not _rows("select 1 from serving.recon_breaks where break_id = :b", b=break_id):
        raise HTTPException(404, "no such break")
    if who.role not in ("operations", "fund_accounting"):
        raise HTTPException(403, "only operations and fund accounting act on breaks")
    with db.begin() as c:
        c.execute(
            text("insert into ops.break_actions (break_id, action, note, actor) values (:b, :a, :n, :w)"),
            {"b": break_id, "a": body.action, "n": body.note, "w": who.actor},
        )
    return _break_rows("b.break_id = :b", b=break_id)[0]


@app.get("/api/cash")
def cash(_: Who) -> list[dict[str, Any]]:
    _served()
    return _rows("select * from serving.cash_now order by due_date, call_id")


# --------------------------------------------------------------------------- funds and statements


@app.get("/api/funds")
def funds_(_: Who) -> list[dict[str, Any]]:
    _served()
    return _rows(
        """select n.*,
             (select count(*) from serving.nav_restatements r where r.fund = n.fund) as restatements
           from serving.fct_fund_nav n
           join (select fund, max(quarter_end) q from serving.fct_fund_nav group by fund) l
             on l.fund = n.fund and l.q = n.quarter_end
           order by n.feeder, n.fund"""
    )


@app.get("/api/funds/{fund}")
def fund(fund: str, _: Who, known_at: dt.date | None = None) -> dict[str, Any]:
    if not FUND.match(fund):
        raise HTTPException(404, "no such fund")
    schema = _served()
    quarters = _rows("select * from serving.fct_fund_nav where fund = :f order by quarter_end", f=fund)
    if not quarters:
        raise HTTPException(404, f"no fund {fund}")
    versions = _rows(
        f"""select file_id, period_end, version, versions, nav, paid_in, distributed, currency, known_from, known_until,
                   parser, unit_scale, file_path
            from {schema}.int_statement_versions where fund = :f order by period_end, version""",
        f=fund,
    )
    out: dict[str, Any] = {
        "fund": fund,
        "quarters": quarters,
        "versions": versions,
        "holds": _rows("select * from serving.statement_holds where fund = :f", f=fund),
        "restatements": _rows("select * from serving.nav_restatements where fund = :f order by period_end", f=fund),
    }
    if known_at:
        # what we knew on that day: the version received by then, per quarter
        out["known_at"] = known_at
        out["as_known"] = [
            v
            for v in versions
            if v["known_from"] <= known_at and (v["known_until"] is None or v["known_until"] > known_at)
        ]
    return out


class Release(BaseModel):
    note: str = Field(min_length=5, max_length=2000)


@app.post("/api/statements/{file_id}/release")
def release(file_id: int, body: Release, who: Who) -> dict[str, Any]:
    if who.role != "fund_accounting":
        raise HTTPException(403, "only fund accounting releases a held statement")
    _served()
    if not _rows("select 1 from serving.statement_holds where file_id = :f", f=file_id):
        raise HTTPException(404, "this statement is not held")
    with db.begin() as c:
        c.execute(
            text(
                "insert into ops.statement_releases (file_id, actor, note) values (:f, :a, :n) on conflict do nothing"
            ),
            {"f": file_id, "a": who.actor, "n": body.note},
        )
    return {"file_id": file_id, "released_by": who.actor, "takes_effect": "next run"}


# --------------------------------------------------------------------------- clients


@app.get("/api/clients")
def clients(
    _: Who,
    q: str | None = Query(None, max_length=40),
    feeder: str | None = Query(None, pattern=r"^[A-Z0-9]{3,4}$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    _served()
    where = "c.total_commitment > 0 and (cast(:q as text) is null or c.client_key like :ql) and (cast(:f as text) is null or exists (select 1 from serving.client_performance p where p.client_key = c.client_key and p.feeder = :f))"
    params = {"q": q, "ql": f"%{(q or '').lower()}%", "f": feeder}
    total = db.scalar(f"select count(*) from serving.dim_clients c where {where}", **params)
    rows = _rows(
        f"""select c.*, (select sum(nav_eur) from serving.client_performance p where p.client_key = c.client_key) as nav_eur,
                  (select count(*) from serving.recon_breaks b where b.client_key = c.client_key) as breaks
            from serving.dim_clients c where {where}
            order by c.total_commitment desc, c.client_key limit :n offset :o""",
        **params,
        n=limit,
        o=offset,
    )
    return {"total": total, "rows": rows}


@app.get("/api/clients/{key}")
def client(key: str, _: Who) -> dict[str, Any]:
    if not KEY.match(key):
        raise HTTPException(404, "no such client")
    _served()
    dim = _rows("select * from serving.dim_clients where client_key = :k", k=key)
    if not dim:
        raise HTTPException(404, "no such client")
    return {
        "client": dim[0],
        "performance": _rows("select * from serving.client_performance where client_key = :k order by feeder", k=key),
        "lookthrough": _rows(
            "select * from serving.fct_client_lookthrough where client_key = :k order by feeder, nav_eur desc", k=key
        ),
        "positions": _rows(
            "select feeder, quarter_end, nav_eur, paid_in_eur, distributed_eur, nav_has_estimates from serving.fct_client_positions where client_key = :k order by feeder, quarter_end",
            k=key,
        ),
        "payments": _rows(
            "select call_id, feeder, due_date, expected_eur, received_eur, provisional_eur, status from serving.fct_payment_status where client_key = :k order by due_date desc",
            k=key,
        ),
        "breaks": _break_rows("b.client_key = :k", k=key),
    }


class Reveal(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


@app.post("/api/clients/{key}/reveal")
def reveal(key: str, body: Reveal, who: Who) -> dict[str, Any]:
    """Who the client is: operations only, with a reason, and logged whether granted or not."""
    if not KEY.match(key):
        raise HTTPException(404, "no such client")
    roles = ",".join(settings()["privacy"]["reveal_roles"])
    with db.begin() as c:
        c.execute(text("select set_config('pmd.reveal_roles', :r, true)"), {"r": roles})
        rows = [
            dict(r._mapping)
            for r in c.execute(
                text("select * from pmd_util.reveal_client(:k, :a, :role, :why)"),
                {"k": key, "a": who.actor, "role": who.role, "why": body.reason},
            )
        ]
    if who.role not in settings()["privacy"]["reveal_roles"]:
        raise HTTPException(403, "your role does not allow seeing who a client is; the attempt is logged")
    if not rows:
        raise HTTPException(404, "no identity for this key (erased, or never a client)")
    return {"client_key": key, **rows[0], "logged": True}


# --------------------------------------------------------------------------- lineage


@app.get("/api/lineage")
def lineage(_: Who) -> dict[str, Any]:
    path = root() / "warehouse" / "target" / "manifest.json"
    if not path.exists():
        raise HTTPException(503, "no dbt manifest yet: run `pmd run`")
    m = json.loads(path.read_text(encoding="utf-8"))
    nodes, edges = [], []
    for uid, n in {**m["nodes"], **m["sources"]}.items():
        kind = n["resource_type"]
        if kind not in ("model", "source"):
            continue
        layer = "source" if kind == "source" else n["fqn"][1] if len(n["fqn"]) > 2 else "model"
        name = f"{n['source_name']}.{n['name']}" if kind == "source" else n["name"]
        nodes.append({"id": uid, "name": name, "layer": layer, "description": (n.get("description") or "")[:300]})
        for dep in n.get("depends_on", {}).get("nodes", []):
            if dep.startswith(("model.", "source.")):
                edges.append({"from": dep, "to": uid})
    return {"nodes": nodes, "edges": edges}


# --------------------------------------------------------------------------- console

web = Path(os.environ.get("PMD_WEB", root() / "web" / "dist"))
if web.exists():
    app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def console(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "no such endpoint")
        file = (web / path).resolve()
        if path and file.is_file() and web.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(web / "index.html")
