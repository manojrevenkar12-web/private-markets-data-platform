"""ISO 20022 camt.053 bank-to-customer statements (any 001.xx version: the namespace is ignored)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from lxml import etree


class CamtError(Exception):
    def __init__(self, rule: str, detail: str):
        super().__init__(f"{rule}: {detail}")
        self.rule = rule
        self.detail = detail


@dataclass
class Entry:
    bank_ref: str
    booking_date: dt.date
    amount: Decimal  # signed
    counterparty_name: str
    counterparty_iban: str
    remittance: str
    status: str


@dataclass
class BankStatement:
    account_iban: str
    statement_date: dt.date
    sequence: int
    opening: Decimal
    closing: Decimal
    entries: list[Entry] = field(default_factory=list)


def _x(el: etree._Element, path: str) -> list[etree._Element]:
    q = "/".join(f"*[local-name()='{p}']" for p in path.split("/"))
    return el.xpath(q)  # type: ignore[no-any-return]


def _t(el: etree._Element, path: str, default: str = "") -> str:
    found = _x(el, path)
    return (found[0].text or "").strip() if found else default


def parse_camt053(path: Path) -> BankStatement:
    try:
        doc = etree.parse(str(path), etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as e:
        raise CamtError("not_xml", str(e)[:200]) from e
    stmts = doc.xpath("//*[local-name()='Stmt']")
    if len(stmts) != 1:
        raise CamtError("one_statement", f"{len(stmts)} statements in the file")
    s = stmts[0]
    iban = _t(s, "Acct/Id/IBAN")
    bals = {}
    for b in _x(s, "Bal"):
        code = _t(b, "Tp/CdOrPrtry/Cd")
        amt = Decimal(_t(b, "Amt"))
        bals[code] = amt if _t(b, "CdtDbtInd") == "CRDT" else -amt
        bals[code + "_date"] = _t(b, "Dt/Dt")  # type: ignore[assignment]
    if "OPBD" not in bals or "CLBD" not in bals:
        raise CamtError("balances_present", "opening or closing balance missing")
    out = BankStatement(
        account_iban=iban,
        statement_date=dt.date.fromisoformat(str(bals.get("CLBD_date"))),
        sequence=int(_t(s, "ElctrncSeqNb", "0") or 0),
        opening=bals["OPBD"],
        closing=bals["CLBD"],
    )
    for n in _x(s, "Ntry"):
        amt = Decimal(_t(n, "Amt"))
        credit = _t(n, "CdtDbtInd") == "CRDT"
        party = "Dbtr" if credit else "Cdtr"
        out.entries.append(
            Entry(
                bank_ref=_t(n, "AcctSvcrRef"),
                booking_date=dt.date.fromisoformat(_t(n, "BookgDt/Dt")),
                amount=amt if credit else -amt,
                counterparty_name=_t(n, f"NtryDtls/TxDtls/RltdPties/{party}/Nm"),
                counterparty_iban=_t(n, f"NtryDtls/TxDtls/RltdPties/{party}Acct/Id/IBAN"),
                remittance=_t(n, "NtryDtls/TxDtls/RmtInf/Ustrd"),
                status=_t(n, "Sts/Cd") or _t(n, "Sts"),
            )
        )
    total = out.opening + sum((e.amount for e in out.entries), Decimal(0))
    if total != out.closing:
        raise CamtError("balances_add_up", f"opening {out.opening} + entries = {total}, closing says {out.closing}")
    if any(e.status != "BOOK" for e in out.entries):
        raise CamtError("booked_only", "entries that are not booked")
    return out
