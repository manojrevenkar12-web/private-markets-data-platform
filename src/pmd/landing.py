"""The file registry: every file that arrives is hashed once. The same bytes under a second name are a
duplicate, never a second load."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

DATE_PREFIX = re.compile(r"(\d{8})")


@dataclass
class Registered:
    file_id: int
    path: Path
    new: bool
    duplicate_of: int | None
    received_on: dt.date


def received_on(path: Path) -> dt.date:
    m = DATE_PREFIX.search(path.name)
    if m:
        try:
            return dt.datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            pass
    return dt.date.fromtimestamp(path.stat().st_mtime)


def register(c: Connection, source: str, path: Path, base: Path) -> Registered:
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    rel = str(path.relative_to(base))
    seen = c.execute(text("select sha256 from ops.file_names where path = :p"), {"p": rel}).scalar()
    existing = c.execute(text("select file_id, path, received_on from ops.files where sha256 = :s"), {"s": sha}).first()
    if seen is None:
        c.execute(text("insert into ops.file_names (path, sha256) values (:p, :s)"), {"p": rel, "s": sha})
    if existing is not None:
        dup = None if existing.path == rel or seen is not None else existing.file_id
        return Registered(existing.file_id, path, False, dup, existing.received_on)
    day = received_on(path)
    fid = c.execute(
        text(
            "insert into ops.files (source, path, sha256, bytes, received_on) values (:src, :p, :s, :b, :d) returning file_id"
        ),
        {"src": source, "p": rel, "s": sha, "b": len(data), "d": day},
    ).scalar_one()
    return Registered(fid, path, True, None, day)


def quarantine(c: Connection, file_id: int, rule: str, detail: str) -> None:
    c.execute(
        text(
            "insert into ops.quarantine (file_id, rule, detail) values (:f, :r, :d) "
            "on conflict (file_id, rule) do update set detail = excluded.detail"
        ),
        {"f": file_id, "r": rule, "d": detail[:2000]},
    )
    c.execute(text("update ops.files set status = 'quarantined' where file_id = :f"), {"f": file_id})


def mark(c: Connection, file_id: int, status: str) -> None:
    c.execute(text("update ops.files set status = :s where file_id = :f"), {"s": status, "f": file_id})
