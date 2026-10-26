"""Held-out statements: written by someone who never saw the parser, from heldout/WRITING_STATEMENTS.md only.

`pmd heldout v1` reads every statement in heldout/v1/statements, checks it against its contract and compares
what it read with heldout/v1/answers. The first run of a set is written to reports/heldout/<set>/first_run.json
once and never rewritten; later runs go to latest.json. Whoever studies a set's failures marks it a regression
set (heldout/<set>/STATUS) and has a new one written.
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .config import root
from .parsers.statements import ParseError, parse_statement, violations

FIELDS = ("fund", "period_end", "currency", "commitment", "paid_in", "distributed", "nav")


def _same(field: str, got: Any, want: Any) -> bool:
    if field in ("fund", "currency"):
        return str(got or "").upper() == str(want or "").upper()
    if field == "period_end":
        return got is not None and got.isoformat() == str(want)
    if got is None or want is None:
        return False
    w = Decimal(str(want))
    return abs(Decimal(str(got)) - w) <= max(Decimal("0.01"), abs(w) * Decimal("0.0000001"))


def score(set_name: str, base: Path | None = None) -> dict[str, Any]:
    base = base or root()
    folder = base / "heldout" / set_name
    status_file = folder / "STATUS"
    result: dict[str, Any] = {
        "set": set_name,
        "status": status_file.read_text().strip() if status_file.exists() else "heldout",
        "run_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }
    files = sorted(p for p in (folder / "statements").iterdir() if p.is_file())
    fields = {f: {"right": 0, "of": 0} for f in FIELDS}
    accept = {"read_right": 0, "of": 0, "rejected_wrongly": 0}
    reject = {"rejected": 0, "of": 0}
    cases = []
    for path in files:
        key_path = folder / "answers" / f"{path.stem}.json"
        if not key_path.exists():
            continue
        key = json.loads(key_path.read_text(encoding="utf-8"))
        try:
            st = parse_statement(path)
            broken = violations(st)
            outcome = "rejected" if broken else "accepted"
            why = "; ".join(f"{r}: {d}" for r, d in broken)
        except ParseError as e:
            st, outcome, why = None, "rejected", f"{e.rule}: {e.detail}"
        case: dict[str, Any] = {"file": path.name, "expect": key["expect"], "outcome": outcome}
        if key["expect"] == "reject":
            reject["of"] += 1
            reject["rejected"] += outcome == "rejected"
        else:
            accept["of"] += 1
            if outcome == "rejected":
                accept["rejected_wrongly"] += 1
                case["why"] = why
            wrong = []
            for f in FIELDS:
                fields[f]["of"] += 1
                got = getattr(st, f) if st is not None else None
                if _same(f, got, key.get(f)):
                    fields[f]["right"] += 1
                else:
                    wrong.append(f)
            if outcome == "accepted" and not wrong:
                accept["read_right"] += 1
            case["wrong_fields"] = wrong
        cases.append(case)
    rate = lambda k, n: round(k / n, 4) if n else None  # noqa: E731
    result["statements"] = len(cases)
    result["accepted_and_read_right"] = {**accept, "rate": rate(accept["read_right"], accept["of"])}
    result["rejected_as_expected"] = {**reject, "rate": rate(reject["rejected"], reject["of"])}
    result["fields"] = {f: {**v, "rate": rate(v["right"], v["of"])} for f, v in fields.items()}
    result["cases"] = cases

    out = base / "reports" / "heldout" / set_name
    out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=1, ensure_ascii=False, default=str)
    first = out / "first_run.json"
    if not first.exists():
        first.write_text(text, encoding="utf-8")
        result["recorded_as_first_run"] = True
    (out / "latest.json").write_text(text, encoding="utf-8")
    return result
