"""pmd: the private-markets data platform from the command line.

pmd run                         load everything new, build, audit, publish (one run)
pmd load                        only the loaders
pmd build --schema S            only dbt, into schema S
pmd diff OLD NEW                what changed between two builds
pmd evaluate [--schema S]       the platform against the simulated world's truth
pmd status                      the last runs and their gates
pmd release FILE_ID --by --note release a held statement
pmd resolve BREAK_ID --by --note
pmd serve [--port 8000]         the API and the console
pmd task NAME --run-id R        one task of the graph (Airflow calls this)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import db


def _print(x: Any) -> None:
    print(json.dumps(x, indent=1, default=str, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pmd", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("load")
    b = sub.add_parser("build")
    b.add_argument("--schema", default="build_dev")
    d = sub.add_parser("diff")
    d.add_argument("old")
    d.add_argument("new")
    e = sub.add_parser("evaluate")
    e.add_argument("--schema")
    sub.add_parser("status")
    r = sub.add_parser("release")
    r.add_argument("file_id", type=int)
    r.add_argument("--by", required=True)
    r.add_argument("--note", required=True)
    rs = sub.add_parser("resolve")
    rs.add_argument("break_id")
    rs.add_argument("--by", required=True)
    rs.add_argument("--note", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--host", default="127.0.0.1")
    t = sub.add_parser("task")
    t.add_argument("name")
    t.add_argument("--run-id", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "run":
        from .flow import run

        out = run()
        g = out["tasks"].get("gates", {})
        p = out["tasks"].get("publish", {})
        print(f"run {out['run_id']} into {out['schema']}")
        for gate in g.get("gates", []):
            mark = "ok  " if gate["passed"] else ("STOP" if gate["severity"] == "block" else "warn")
            print(f"  {mark} {gate['name']}: {gate['detail']}")
        print("published" if p.get("published") else f"not published: {p.get('reason') or g.get('blocked')}")
        return 0 if p.get("published") else 1
    if args.cmd == "load":
        from .flow import RunContext, order

        ctx = RunContext("load")
        for task in order():
            if task.name.startswith(("bootstrap", "load_", "consume_")):
                _print({task.name: task.fn(ctx)})
    elif args.cmd == "build":
        from .warehouse import build

        res = build(args.schema)
        _print(res.__dict__)
        return 0 if res.ok else 1
    elif args.cmd == "diff":
        from .publish import diff

        _print(diff(args.old, args.new))
    elif args.cmd == "evaluate":
        from .evaluate import evaluate
        from .publish import published_schema

        _print(evaluate(args.schema or published_schema() or "serving"))
    elif args.cmd == "status":
        _print(
            db.rows(
                "select run_id, status, build_schema, as_of, started_at, finished_at, gates from ops.runs order by started_at desc limit 5"
            )
        )
    elif args.cmd == "release":
        with db.begin() as c:
            c.exec_driver_sql(
                "insert into ops.statement_releases (file_id, actor, note) values (%(f)s, %(a)s, %(n)s) on conflict do nothing",
                {"f": args.file_id, "a": args.by, "n": args.note},
            )
        print("released; the next run uses the statement")
    elif args.cmd == "resolve":
        with db.begin() as c:
            c.exec_driver_sql(
                "insert into ops.break_actions (break_id, action, note, actor) values (%(b)s, 'resolve', %(n)s, %(a)s)",
                {"b": args.break_id, "a": args.by, "n": args.note},
            )
        print("resolved; the next run shows it")
    elif args.cmd == "serve":
        import uvicorn

        uvicorn.run("pmd.api:app", host=args.host, port=args.port)
    elif args.cmd == "task":
        from .flow import run_task

        _print(run_task(args.name, args.run_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
