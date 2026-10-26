"""Writes the world the way its sources would hand it over, and the answer key beside it.

data/landing/gp_statements/   quarterly capital account statements: PDF (English, German), Excel, CSV
data/landing/bank/<iban>/     custodian statements, ISO 20022 camt.053, one per business day with bookings
data/landing/crm/             client export (personal data), erasure requests
data/landing/ops/             commitments, capital calls and distributions issued to clients
data/landing/market/          EUR/USD reference rates
data/landing/events/          instant payment notifications, as the Kafka topic carries them
data/truth/                   what really happened; only pmd.evaluate reads it
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import random
from decimal import Decimal
from pathlib import Path
from typing import Any

from .world import TargetQuarter, World, business_day

MONTHS_EN = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def _en(x: Decimal) -> str:
    return f"{x:,.2f}"


def _de(x: Decimal) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _en_date(d: dt.date) -> str:
    return f"{MONTHS_EN[d.month - 1]} {d.day}, {d.year}"


def _slug(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in s).strip("-")


# --------------------------------------------------------------------------- GP statements


def _pdf(lines: list[tuple[str, str]], text_layer: bool = True) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    y = 800
    for label, value in lines:
        if not text_layer:
            # a scan: the page shows bars where text would be, no text a parser can read
            c.rect(60, y - 2, 6 * len(label + value) * 0.7, 9, fill=1, stroke=0)
        else:
            c.setFont("Helvetica-Bold" if not value else "Helvetica", 10)
            c.drawString(60, y, label)
            if value:
                c.drawRightString(530, y, value)
        y -= 18 if value else 22
    c.showPage()
    c.save()
    return buf.getvalue()


def statement_pdf_en(
    investor: str, fund: dict[str, Any], tq: TargetQuarter, issued: dt.date, scan: bool = False
) -> bytes:
    cur = tq.currency
    lines = [
        (fund["gp"], ""),
        (f"{fund['name']}, L.P.", ""),
        ("Capital Account Statement", ""),
        (f"Investor: {investor}", ""),
        (f"For the period ended {_en_date(tq.period_end)}", ""),
        (f"All amounts in {cur}", ""),
        ("Total commitment", _en(tq.commitment)),
        ("Contributions to date", _en(tq.paid_in)),
        ("Distributions to date", _en(tq.distributions)),
        ("Capital account balance (NAV)", _en(tq.nav)),
        ("Unfunded commitment", _en(tq.commitment - tq.paid_in)),
        (f"Statement date: {_en_date(issued)}", ""),
    ]
    return _pdf(lines, text_layer=not scan)


def statement_pdf_de(investor: str, fund: dict[str, Any], tq: TargetQuarter, issued: dt.date) -> bytes:
    cur = tq.currency
    lines = [
        (fund["gp"], ""),
        (f"{fund['name']} SCSp", ""),
        (f"Kapitalkontoauszug zum {tq.period_end:%d.%m.%Y}", ""),
        (f"Anleger: {investor}", ""),
        (f"Währung: {cur}", ""),
        ("Zeichnungsbetrag", f"{_de(tq.commitment)} {cur}"),
        ("Eingezahltes Kapital", f"{_de(tq.paid_in)} {cur}"),
        ("Ausschüttungen kumuliert", f"{_de(tq.distributions)} {cur}"),
        ("Nettoinventarwert (NAV)", f"{_de(tq.nav)} {cur}"),
        ("Offene Einzahlungsverpflichtung", f"{_de(tq.commitment - tq.paid_in)} {cur}"),
        (f"Erstellt am {issued:%d.%m.%Y}", ""),
    ]
    return _pdf(lines)


def statement_xlsx_de(investor: str, fund: dict[str, Any], tq: TargetQuarter, issued: dt.date, teur: bool) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Kapitalkonto"
    scale = Decimal(1000) if teur else Decimal(1)
    unit = "TEUR" if teur else tq.currency
    ws.append([fund["name"]])
    ws.append(["Kapitalkontoauszug"])
    ws.append(["Anleger", investor])
    ws.append(["Stichtag", tq.period_end])
    ws.append([f"Beträge in {unit}"])
    ws.append([])
    for label, val in (
        ("Zeichnungsbetrag", tq.commitment),
        ("Eingezahltes Kapital", tq.paid_in),
        ("Ausschüttungen", tq.distributions),
        ("Nettoinventarwert", tq.nav),
        ("Offene Einzahlungsverpflichtung", tq.commitment - tq.paid_in),
    ):
        ws.append([label, float(round(val / scale, 3 if teur else 2))])
    ws.append([])
    ws.append(["Erstellt am", issued])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


CSV_DIALECTS = {
    # fund -> (delimiter, header, date format); every GP exports a little differently
    "FJD3": (
        ";",
        ["lp_name", "fund_name", "as_of", "ccy", "commitment", "contributed", "distributed", "nav", "statement_date"],
        "%Y-%m-%d",
    ),
    "ORI9": (
        ",",
        [
            "Investor",
            "Fund",
            "Period End",
            "Currency",
            "Commitment",
            "Paid-In Capital",
            "Distributions",
            "Net Asset Value",
            "Report Date",
        ],
        "%m/%d/%Y",
    ),
    "TID1": (
        ",",
        ["investor", "fund", "reference_date", "currency", "commitment", "paid_in", "distributions", "nav", "issued"],
        "%d/%m/%Y",
    ),
    "CRE4": (
        ",",
        [
            "investor_name",
            "fund_name",
            "period_end",
            "currency",
            "total_commitment",
            "called_capital",
            "distributions",
            "capital_account",
            "statement_date",
        ],
        "%Y-%m-%d",
    ),
}


def statement_csv(
    fund_id: str, investor: str, fund: dict[str, Any], tq: TargetQuarter, issued: dt.date, scale: int = 1
) -> bytes:
    delim, header, fmt = CSV_DIALECTS[fund_id]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator="\n")
    w.writerow(header)
    w.writerow(
        [
            investor,
            fund["name"],
            tq.period_end.strftime(fmt),
            tq.currency,
            *(f"{v / scale:.2f}" for v in (tq.commitment, tq.paid_in, tq.distributions, tq.nav)),
            issued.strftime(fmt),
        ]
    )
    return buf.getvalue().encode("utf-8")


# --------------------------------------------------------------------------- bank (camt.053)


def camt053(iban: str, day: dt.date, opening: Decimal, entries: list[Any], seq: int) -> bytes:
    from lxml import etree

    ns = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08"
    E = lambda tag, *kids, text=None, **attrs: _el(etree, ns, tag, kids, text, attrs)  # noqa: E731
    closing = opening + sum((e.amount for e in entries), Decimal(0))

    def bal(code: str, amount: Decimal) -> Any:
        return E(
            "Bal",
            E("Tp", E("CdOrPrtry", E("Cd", text=code))),
            E("Amt", text=f"{abs(amount):.2f}", Ccy="EUR"),
            E("CdtDbtInd", text="CRDT" if amount >= 0 else "DBIT"),
            E("Dt", E("Dt", text=day.isoformat())),
        )

    ntries = []
    for e in entries:
        party = "Dbtr" if e.amount > 0 else "Cdtr"
        ntries.append(
            E(
                "Ntry",
                E("Amt", text=f"{abs(e.amount):.2f}", Ccy="EUR"),
                E("CdtDbtInd", text="CRDT" if e.amount > 0 else "DBIT"),
                E("Sts", E("Cd", text="BOOK")),
                E("BookgDt", E("Dt", text=e.booked.isoformat())),
                E("ValDt", E("Dt", text=e.booked.isoformat())),
                E("AcctSvcrRef", text=e.id),
                E(
                    "NtryDtls",
                    E(
                        "TxDtls",
                        E(
                            "RltdPties",
                            E(party, E("Nm", text=e.counterparty_name)),
                            E(f"{party}Acct", E("Id", E("IBAN", text=e.counterparty_iban))),
                        ),
                        E("RmtInf", E("Ustrd", text=e.remittance)),
                    ),
                ),
            )
        )
    doc = E(
        "Document",
        E(
            "BkToCstmrStmt",
            E(
                "GrpHdr",
                E("MsgId", text=f"STMT-{iban[-6:]}-{day:%Y%m%d}"),
                E("CreDtTm", text=f"{business_day(day + dt.timedelta(days=1))}T06:30:00"),
            ),
            E(
                "Stmt",
                E("Id", text=f"{iban[-6:]}-{seq:05d}"),
                E("ElctrncSeqNb", text=str(seq)),
                E("Acct", E("Id", E("IBAN", text=iban)), E("Ccy", text="EUR")),
                bal("OPBD", opening),
                bal("CLBD", closing),
                *ntries,
            ),
        ),
    )
    return etree.tostring(doc, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _el(etree: Any, ns: str, tag: str, kids: tuple[Any, ...], text: str | None, attrs: dict[str, str]) -> Any:
    el = etree.Element(f"{{{ns}}}{tag}", nsmap={None: ns} if tag == "Document" else None, **attrs)
    if text is not None:
        el.text = text
    for k in kids:
        el.append(k)
    return el


# --------------------------------------------------------------------------- everything


def write_all(w: World, data: Path, seed: int) -> dict[str, int]:
    rnd = random.Random(f"{seed}-writers")
    land = data / "landing"
    truth = data / "truth"
    for sub in ("gp_statements", "bank", "crm", "ops", "market", "events"):
        (land / sub).mkdir(parents=True, exist_ok=True)
    truth.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    counts["statements"] = _write_statements(w, land / "gp_statements", truth, rnd)
    counts["bank_files"] = _write_bank(w, land / "bank")
    counts["events"] = _write_events(w, land / "events", rnd)
    _write_crm_ops_market(w, land)
    _write_truth(w, truth)
    counts["clients"] = len(w.clients)
    counts["commitments"] = len(w.commitments)
    return counts


def _write_statements(w: World, out: Path, truth: Path, rnd: random.Random) -> int:
    feeders = w.funds["feeders"]
    rows: list[dict[str, Any]] = []
    n = 0
    latest_due: dict[str, dt.date] = {}
    for tq in w.target_quarters:
        if tq.period_end < w.today - dt.timedelta(days=90):
            latest_due[tq.fund] = max(latest_due.get(tq.fund, tq.period_end), tq.period_end)

    def emit(name: str, data: bytes) -> None:
        nonlocal n
        (out / name).write_bytes(data)
        n += 1

    for tq in w.target_quarters:
        fid, fund = w.target(tq.fund)
        investor = f"{feeders[fid]['name']} GmbH & Co. KG"
        kind = fund["statement"]
        lag = rnd.randint(28, 55) if kind == "csv" else rnd.randint(40, 82)
        issued = business_day(tq.period_end + dt.timedelta(days=lag))
        flags: list[str] = []
        delivered = issued <= w.today
        if tq.fund == "HAL2" and tq.period_end == latest_due.get("HAL2"):
            delivered = False
            flags.append("statement_late")
        record = {
            "fund": tq.fund,
            "period_end": tq.period_end.isoformat(),
            "currency": tq.currency,
            "commitment": str(tq.commitment),
            "paid_in": str(tq.paid_in),
            "distributed": str(tq.distributions),
            "nav": str(tq.nav),
            "issued": issued.isoformat(),
            "delivered": delivered,
            "flags": flags,
        }
        rows.append(record)
        if not delivered:
            for f in flags:
                w.planted.append({"kind": f, "fund": tq.fund, "period_end": tq.period_end.isoformat()})
            continue
        stem = (
            f"{issued:%Y%m%d}_{_slug(fund['gp'])}_{hashlib.sha1(f'{tq.fund}{tq.period_end}'.encode()).hexdigest()[:6]}"
        )
        qkey = (tq.fund, tq.period_end)
        if kind == "pdf_en":
            if qkey == ("LUM5", _nth_quarter(w, "LUM5", -4)):
                emit(f"{stem}.pdf", statement_pdf_en(investor, fund, tq, issued, scan=True))
                flags.append("scan_resent")
                resent = business_day(issued + dt.timedelta(days=12))
                if resent <= w.today:
                    emit(
                        f"{resent:%Y%m%d}_{_slug(fund['gp'])}_resent.pdf", statement_pdf_en(investor, fund, tq, resent)
                    )
                    record["issued"] = resent.isoformat()
            else:
                emit(f"{stem}.pdf", statement_pdf_en(investor, fund, tq, issued))
        elif kind == "pdf_de":
            emit(f"{stem}.pdf", statement_pdf_de(investor, fund, tq, issued))
        elif kind == "xlsx_de":
            if qkey == ("KES4", _nth_quarter(w, "KES4", -4)):
                # first sent with a NAV that was too high; the corrected statement follows
                wrong = TargetQuarter(**{**tq.__dict__, "nav": (tq.nav * Decimal("1.065")).quantize(Decimal("0.01"))})
                emit(f"{stem}.xlsx", statement_xlsx_de(investor, fund, wrong, issued, teur=False))
                again = business_day(issued + dt.timedelta(days=41))
                emit(
                    f"{again:%Y%m%d}_{_slug(fund['gp'])}_korrektur.xlsx",
                    statement_xlsx_de(investor, fund, tq, again, teur=False),
                )
                flags.append("restated")
                record["first_nav"] = str(wrong.nav)
                record["issued"] = again.isoformat()
            else:
                emit(f"{stem}.xlsx", statement_xlsx_de(investor, fund, tq, issued, teur=tq.fund == "SPR2"))
        else:
            if qkey == ("ORI9", _nth_quarter(w, "ORI9", -1)):
                emit(f"{stem}.csv", statement_csv(tq.fund, investor, fund, tq, issued, scale=1000))
                flags.append("thousands_unlabelled")
            else:
                emit(f"{stem}.csv", statement_csv(tq.fund, investor, fund, tq, issued))
                if qkey == ("FJD3", _nth_quarter(w, "FJD3", -3)):
                    emit(f"{stem}_copy.csv", statement_csv(tq.fund, investor, fund, tq, issued))
                    flags.append("duplicate_file")
        for f in flags:
            w.planted.append({"kind": f, "fund": tq.fund, "period_end": tq.period_end.isoformat()})
    (truth / "statements.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return n


def _nth_quarter(w: World, fund: str, k: int) -> dt.date | None:
    """The k-th quarter end counted from the newest one whose statement is due (k=-1 the newest)."""
    ends = sorted(
        {
            tq.period_end
            for tq in w.target_quarters
            if tq.fund == fund and tq.period_end < w.today - dt.timedelta(days=60)
        }
    )
    return ends[k] if len(ends) >= -k else None


def _write_bank(w: World, out: Path) -> int:
    n = 0
    for fid, f in w.funds["feeders"].items():
        iban = f["collection_account"]
        acct = out / iban
        acct.mkdir(parents=True, exist_ok=True)
        balance = Decimal(0)
        by_day: dict[dt.date, list[Any]] = {}
        for p in w.payments:
            if p.feeder == fid:
                by_day.setdefault(p.booked, []).append(p)
        for seq, day in enumerate(sorted(by_day), 1):
            arrives = business_day(day + dt.timedelta(days=1))
            if arrives > w.today:
                break
            entries = by_day[day]
            (acct / f"camt053_{iban[-6:]}_{day:%Y%m%d}.xml").write_bytes(camt053(iban, day, balance, entries, seq))
            balance += sum((e.amount for e in entries), Decimal(0))
            n += 1
    return n


def _write_events(w: World, out: Path, rnd: random.Random) -> int:
    """Instant payment notifications for client receipts in the last weeks; at-least-once, slightly out of order."""
    since = w.today - dt.timedelta(days=21)
    events = []
    ibans = {f["collection_account"]: fid for fid, f in w.funds["feeders"].items()}
    accounts = {fid: iban for iban, fid in ibans.items()}
    for p in w.payments:
        if p.amount <= 0 or p.booked < since or p.booked > w.today or p.received_at is None:
            continue
        ev = {
            "event_id": f"evt-{hashlib.sha1(p.id.encode()).hexdigest()[:16]}",
            "type": "payment.received",
            "account_iban": accounts[p.feeder],
            "amount": str(p.amount),
            "currency": "EUR",
            "debtor_name": p.counterparty_name,
            "debtor_iban": p.counterparty_iban,
            "remittance": p.remittance,
            "received_at": p.received_at.isoformat(),
            "bank_ref": p.id,
        }
        events.append(ev)
        if rnd.random() < 0.03:
            events.append(dict(ev))  # redelivered
    events.sort(key=lambda e: e["received_at"])
    for i in range(0, len(events) - 1, 7):  # a little reordering across partitions
        if rnd.random() < 0.4:
            events[i], events[i + 1] = events[i + 1], events[i]
    with (out / "payments.jsonl").open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(events)


def _write_crm_ops_market(w: World, land: Path) -> None:
    with (land / "crm" / f"clients_{w.today:%Y%m%d}.csv").open("w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh)
        cw.writerow(
            [
                "client_id",
                "first_name",
                "last_name",
                "email",
                "phone",
                "birth_date",
                "street",
                "postal_code",
                "city",
                "country",
                "iban",
                "tax_id",
                "segment",
                "risk_profile",
                "onboarded_at",
                "advisor",
                "status",
            ]
        )
        for c in [*w.clients, *w.prospects]:
            cw.writerow(
                [
                    c.id,
                    c.first_name,
                    c.last_name,
                    c.email,
                    c.phone,
                    c.birth_date,
                    c.street,
                    c.postal_code,
                    c.city,
                    c.country,
                    c.iban,
                    c.tax_id,
                    c.segment,
                    c.risk_profile,
                    c.onboarded_at,
                    c.advisor,
                    "prospect" if c in w.prospects else "client",
                ]
            )
    with (land / "crm" / "erasure_requests.csv").open("w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh)
        cw.writerow(["request_id", "client_id", "requested_at"])
        for i, (cid, at) in enumerate(w.erasure_requests, 1):
            cw.writerow([f"ER-{i:04d}", cid, at])
    with (land / "ops" / "commitments.csv").open("w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh)
        cw.writerow(["subscription_id", "client_id", "feeder", "amount_eur", "signed_at"])
        for cm in w.commitments:
            cw.writerow([cm.id, cm.client, cm.feeder, f"{cm.amount:.2f}", cm.signed_at])
    with (land / "ops" / "capital_calls.csv").open("w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh)
        cw.writerow(["call_id", "feeder", "notice_date", "due_date", "percent_of_commitment"])
        for call in w.feeder_calls:
            if call.notice_date <= w.today:
                cw.writerow([call.id, call.feeder, call.notice_date, call.due_date, f"{call.percent:.2f}"])
    with (land / "ops" / "distributions.csv").open("w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh)
        cw.writerow(["distribution_id", "feeder", "pay_date", "percent_of_commitment"])
        for fd in w.feeder_distributions:
            if fd.pay_date <= w.today:
                cw.writerow([fd.id, fd.feeder, fd.pay_date, f"{fd.percent:.2f}"])
    with (land / "ops" / "target_commitments.csv").open("w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh)
        cw.writerow(["feeder", "fund", "currency", "commitment"])
        for fid, f in w.funds["feeders"].items():
            for tid, t in f["targets"].items():
                if tid in w.target_commitments:
                    cw.writerow([fid, tid, t["currency"], f"{w.target_commitments[tid]:.2f}"])
    with (land / "market" / "eurusd.csv").open("w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh)
        cw.writerow(["date", "usd_per_eur"])
        for d, r in sorted(w.fx.items()):
            if d <= w.today:
                cw.writerow([d, r])


def _write_truth(w: World, truth: Path) -> None:
    feeders = {fid: f["name"] for fid, f in w.funds["feeders"].items()}
    nav_eur = []
    for tq in w.target_quarters:
        if tq.period_end > w.today:
            continue
        rate = w.usd_per_eur(tq.period_end) if tq.currency == "USD" else Decimal(1)
        nav_eur.append(
            {
                "fund": tq.fund,
                "period_end": tq.period_end.isoformat(),
                "nav_eur": str((tq.nav / rate).quantize(Decimal("0.01"))),
            }
        )
    payload = {
        "today": w.today.isoformat(),
        "feeders": feeders,
        "planted": w.planted,
        "target_nav_eur": nav_eur,
        "commitments": [{"client": c.client, "feeder": c.feeder, "amount": str(c.amount)} for c in w.commitments],
        "payments": [
            {
                "id": p.id,
                "feeder": p.feeder,
                "booked": p.booked.isoformat(),
                "amount": str(p.amount),
                "kind": p.kind,
                "client": p.client,
                "call": p.call,
                "fund": p.fund,
                "anomaly": p.anomaly,
            }
            for p in w.payments
            if p.booked <= w.today
        ],
    }
    (truth / "world.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
