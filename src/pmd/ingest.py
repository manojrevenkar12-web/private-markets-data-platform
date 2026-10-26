"""Loaders: from landing files to the raw schema, with contracts checked and personal data split off.

Every loader registers each file by its hash first, so a re-run loads nothing twice and a file re-sent under
another name is recorded as a duplicate. A file that breaks its contract goes to ops.quarantine with the rule.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from . import db
from .config import feeder_accounts, funds, landing_dir, target_funds, today
from .landing import mark, quarantine, register
from .parsers.camt import CamtError, parse_camt053
from .parsers.statements import ParseError, parse_statement, violations
from .privacy import age_band, client_key, counterparty_key, iban_valid, redact_remittance


@dataclass
class LoadReport:
    source: str
    loaded: int = 0
    skipped: int = 0
    duplicates: int = 0
    quarantined: int = 0
    rows: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _files(folder: Path, *patterns: str) -> list[Path]:
    out: list[Path] = []
    for p in patterns:
        out.extend(folder.rglob(p))
    return sorted(set(out))


# --------------------------------------------------------------------------- GP statements


def load_statements(base: Path | None = None) -> LoadReport:
    base = base or landing_dir()
    rep = LoadReport("gp_statements")
    for path in _files(base / "gp_statements", "*.pdf", "*.xlsx", "*.csv", "*.txt", "*.md"):
        with db.begin() as c:
            reg = register(c, "gp_statement", path, base)
            if not reg.new:
                if reg.duplicate_of:
                    rep.duplicates += 1
                else:
                    rep.skipped += 1
                continue
            try:
                st = parse_statement(path)
            except ParseError as e:
                quarantine(c, reg.file_id, e.rule, e.detail)
                rep.quarantined += 1
                continue
            broken = violations(st)
            if broken:
                for rule, detail in broken:
                    quarantine(c, reg.file_id, rule, detail)
                rep.quarantined += 1
                continue
            c.execute(
                text(
                    """insert into raw.gp_statements (file_id, fund, period_end, currency, commitment, paid_in,
                       distributed, nav, unfunded, statement_date, unit_scale, received_on, parser)
                       values (:file_id, :fund, :period_end, :currency, :commitment, :paid_in, :distributed, :nav,
                       :unfunded, :statement_date, :unit_scale, :received_on, :parser)"""
                ),
                {**st.as_dict(), "file_id": reg.file_id, "received_on": reg.received_on, "parser": st.parser},
            )
            mark(c, reg.file_id, "loaded")
            rep.loaded += 1
    return rep


# --------------------------------------------------------------------------- bank


def load_bank(base: Path | None = None) -> LoadReport:
    base = base or landing_dir()
    rep = LoadReport("bank")
    accounts = feeder_accounts()
    for path in _files(base / "bank", "*.xml"):
        with db.begin() as c:
            reg = register(c, "camt053", path, base)
            if not reg.new:
                rep.duplicates += bool(reg.duplicate_of)
                rep.skipped += not reg.duplicate_of
                continue
            try:
                stmt = parse_camt053(path)
            except CamtError as e:
                quarantine(c, reg.file_id, e.rule, e.detail)
                rep.quarantined += 1
                continue
            if stmt.account_iban not in accounts:
                quarantine(c, reg.file_id, "account_known", f"{stmt.account_iban[:4]}… is not a feeder account")
                rep.quarantined += 1
                continue
            c.execute(
                text("insert into raw.bank_statements values (:f, :a, :d, :s, :o, :cl) on conflict do nothing"),
                {
                    "f": reg.file_id,
                    "a": stmt.account_iban,
                    "d": stmt.statement_date,
                    "s": stmt.sequence,
                    "o": stmt.opening,
                    "cl": stmt.closing,
                },
            )
            entries, vault = [], {}
            for e in stmt.entries:
                ck = counterparty_key(e.counterparty_iban) if e.counterparty_iban else counterparty_key("UNKNOWN")
                vault[ck] = {"k": ck, "n": e.counterparty_name, "i": e.counterparty_iban}
                red, call, client = redact_remittance(e.remittance)
                entries.append(
                    {
                        "r": e.bank_ref,
                        "f": reg.file_id,
                        "a": stmt.account_iban,
                        "d": e.booking_date,
                        "m": e.amount,
                        "ck": ck,
                        "rem": red,
                        "call": call,
                        "cl": client,
                    }
                )
            if entries:
                c.execute(
                    text(
                        """insert into raw.bank_entries (bank_ref, file_id, account_iban, booking_date, amount,
                           counterparty_key, remittance, ref_call_id, ref_client_key)
                           values (:r, :f, :a, :d, :m, :ck, :rem, :call, :cl) on conflict (bank_ref) do nothing"""
                    ),
                    entries,
                )
                c.execute(
                    text(
                        "insert into pii.counterparty_vault values (:k, :n, :i) on conflict (counterparty_key) do nothing"
                    ),
                    list(vault.values()),
                )
            mark(c, reg.file_id, "loaded")
            rep.loaded += 1
            rep.rows += len(entries)
    return rep


# --------------------------------------------------------------------------- CRM and erasure


def _erased(c: Connection) -> set[str]:
    return {r[0] for r in c.execute(text("select client_key from ops.erasure_requests where status = 'erased'"))}


def load_crm(base: Path | None = None) -> LoadReport:
    base = base or landing_dir()
    rep = LoadReport("crm")
    exports = _files(base / "crm", "clients_*.csv")
    if not exports:
        rep.notes.append("no CRM export")
        return rep
    path = exports[-1]  # the newest snapshot is the truth about clients
    with db.begin() as c:
        reg = register(c, "crm", path, base)
        if not reg.new:
            rep.skipped += 1
        else:
            erased = _erased(c)
            bad: list[str] = []
            clients, vault, accounts = [], [], []
            with path.open(encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    key = client_key(row["client_id"])
                    if key in erased:
                        continue  # an erasure is final: the snapshot may still contain the person
                    if not iban_valid(row["iban"]):
                        bad.append(key)
                        continue
                    born = dt.date.fromisoformat(row["birth_date"]) if row.get("birth_date") else None
                    clients.append(
                        {
                            "k": key,
                            "seg": row["segment"],
                            "risk": row["risk_profile"],
                            "country": row["country"],
                            "age": age_band(born.year, today().year) if born else None,
                            "on": row["onboarded_at"] or None,
                            "adv": row["advisor"],
                            "st": row["status"],
                        }
                    )
                    vault.append(
                        {
                            "k": key,
                            "id": row["client_id"],
                            "fn": row["first_name"],
                            "ln": row["last_name"],
                            "em": row["email"],
                            "ph": row["phone"],
                            "bd": born,
                            "st": row["street"],
                            "pc": row["postal_code"],
                            "ci": row["city"],
                            "ib": row["iban"],
                            "tx": row["tax_id"],
                        }
                    )
                    accounts.append({"ck": counterparty_key(row["iban"]), "k": key})
            c.execute(text("truncate raw.clients, raw.client_accounts"))
            c.execute(
                text(
                    "insert into raw.clients (client_key, segment, risk_profile, country, age_band, onboarded_on, "
                    "advisor, status) values (:k, :seg, :risk, :country, :age, :on, :adv, :st)"
                ),
                clients,
            )
            c.execute(text("insert into raw.client_accounts values (:ck, :k) on conflict do nothing"), accounts)
            c.execute(
                text(
                    """insert into pii.client_vault values (:k, :id, :fn, :ln, :em, :ph, :bd, :st, :pc, :ci, :ib, :tx)
                       on conflict (client_key) do update set first_name = excluded.first_name,
                       last_name = excluded.last_name, email = excluded.email, phone = excluded.phone,
                       birth_date = excluded.birth_date, street = excluded.street, postal_code = excluded.postal_code,
                       city = excluded.city, iban = excluded.iban, tax_id = excluded.tax_id"""
                ),
                vault,
            )
            if bad:
                quarantine(c, reg.file_id, "iban_checksum", f"{len(bad)} rows: " + ", ".join(bad[:20]))
            mark(c, reg.file_id, "loaded")
            rep.loaded += 1
            rep.rows = len(clients)
    rep.notes += apply_erasures(base)
    return rep


def apply_erasures(base: Path | None = None) -> list[str]:
    """GDPR art. 17 requests. A prospect is erased everywhere; an investor's data is kept under the retention
    duties of anti-money-laundering and commercial law (GwG §8, HGB §257) and the request is recorded as on
    hold with that reason."""
    base = base or landing_dir()
    path = base / "crm" / "erasure_requests.csv"
    notes: list[str] = []
    if not path.exists():
        return notes
    with db.begin() as c, path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = client_key(row["client_id"])
            if c.execute(
                text("select 1 from ops.erasure_requests where request_id = :r"), {"r": row["request_id"]}
            ).first():
                continue
            invested = c.execute(
                text("select count(*) from raw.commitments where client_key = :k"), {"k": key}
            ).scalar()
            if invested:
                status, reason = (
                    "retention_hold",
                    "investor: records kept for the statutory retention period (GwG §8, HGB §257)",
                )
            else:
                status, reason = "erased", "prospect without commitments: personal data deleted"
                iban_key = c.execute(
                    text("select counterparty_key from raw.client_accounts where client_key = :k"), {"k": key}
                ).scalar()
                c.execute(text("delete from pii.client_vault where client_key = :k"), {"k": key})
                c.execute(text("delete from raw.client_accounts where client_key = :k"), {"k": key})
                c.execute(text("delete from raw.clients where client_key = :k"), {"k": key})
                if iban_key:
                    c.execute(text("delete from pii.counterparty_vault where counterparty_key = :c"), {"c": iban_key})
            c.execute(
                text("insert into ops.erasure_requests values (:r, :k, :d, :s, :why)"),
                {"r": row["request_id"], "k": key, "d": row["requested_at"], "s": status, "why": reason},
            )
            notes.append(f"{row['request_id']}: {status}")
    return notes


# --------------------------------------------------------------------------- fund operations and market data


def _snapshot(c: Connection, base: Path, rel: str, source: str) -> tuple[Path, bool]:
    path = base / rel
    if not path.exists():
        return path, False
    reg = register(c, source, path, base)
    if reg.new:
        mark(c, reg.file_id, "loaded")
    return path, reg.new


def load_reference() -> None:
    """Feeders and target funds from config/funds.yaml: the master data every model joins to."""
    with db.begin() as c:
        c.execute(text("truncate raw.feeders, raw.target_funds"))
        for fid, f in funds()["feeders"].items():
            c.execute(
                text("insert into raw.feeders values (:f, :n, :a, :d, :m)"),
                {"f": fid, "n": f["name"], "a": f["collection_account"], "d": f["first_close"], "m": f["min_ticket"]},
            )
        for tid, t in target_funds().items():
            c.execute(
                text("insert into raw.target_funds values (:t, :f, :n, :g, :r, :s, :c)"),
                {
                    "t": tid,
                    "f": t["feeder"],
                    "n": t["name"],
                    "g": t["gp"],
                    "r": t["region"],
                    "s": t["strategy"],
                    "c": t["currency"],
                },
            )


def load_ops(base: Path | None = None) -> LoadReport:
    base = base or landing_dir()
    rep = LoadReport("ops")
    load_reference()
    with db.begin() as c:
        path, new = _snapshot(c, base, "ops/commitments.csv", "commitments")
        if new:
            with path.open(encoding="utf-8") as fh:
                rows = [
                    {
                        "s": r["subscription_id"],
                        "k": client_key(r["client_id"]),
                        "f": r["feeder"],
                        "a": Decimal(r["amount_eur"]),
                        "d": r["signed_at"],
                    }
                    for r in csv.DictReader(fh)
                ]
            c.execute(text("truncate raw.commitments"))
            c.execute(text("insert into raw.commitments values (:s, :k, :f, :a, :d)"), rows)
            rep.rows += len(rows)
            rep.loaded += 1
        path, new = _snapshot(c, base, "ops/capital_calls.csv", "capital_calls")
        if new:
            with path.open(encoding="utf-8") as fh:
                rows = [
                    {
                        "i": r["call_id"],
                        "f": r["feeder"],
                        "n": r["notice_date"],
                        "d": r["due_date"],
                        "p": Decimal(r["percent_of_commitment"]),
                    }
                    for r in csv.DictReader(fh)
                ]
            c.execute(text("truncate raw.capital_calls"))
            c.execute(text("insert into raw.capital_calls values (:i, :f, :n, :d, :p)"), rows)
            rep.rows += len(rows)
            rep.loaded += 1
        path, new = _snapshot(c, base, "ops/distributions.csv", "distributions")
        if new:
            with path.open(encoding="utf-8") as fh:
                rows = [
                    {
                        "i": r["distribution_id"],
                        "f": r["feeder"],
                        "d": r["pay_date"],
                        "p": Decimal(r["percent_of_commitment"]),
                    }
                    for r in csv.DictReader(fh)
                ]
            c.execute(text("truncate raw.distributions"))
            if rows:
                c.execute(text("insert into raw.distributions values (:i, :f, :d, :p)"), rows)
            rep.rows += len(rows)
            rep.loaded += 1
        path, new = _snapshot(c, base, "ops/target_commitments.csv", "target_commitments")
        if new:
            with path.open(encoding="utf-8") as fh:
                rows = [
                    {"t": r["fund"], "f": r["feeder"], "c": r["currency"], "a": Decimal(r["commitment"])}
                    for r in csv.DictReader(fh)
                ]
            c.execute(text("truncate raw.target_commitments"))
            c.execute(text("insert into raw.target_commitments values (:t, :f, :c, :a)"), rows)
            rep.rows += len(rows)
            rep.loaded += 1
    return rep


def load_market(base: Path | None = None) -> LoadReport:
    base = base or landing_dir()
    rep = LoadReport("market")
    with db.begin() as c:
        path, new = _snapshot(c, base, "market/eurusd.csv", "fx")
        if new:
            with path.open(encoding="utf-8") as fh:
                rows = [{"d": r["date"], "r": Decimal(r["usd_per_eur"])} for r in csv.DictReader(fh)]
            c.execute(
                text(
                    "insert into raw.fx_rates values (:d, :r) on conflict (rate_date) do update set usd_per_eur = excluded.usd_per_eur"
                ),
                rows,
            )
            rep.rows = len(rows)
            rep.loaded = 1
    return rep
