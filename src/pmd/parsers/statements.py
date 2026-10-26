"""Quarterly capital account statements, whatever shape a fund manager sends them in.

The parser reads labels, not layouts. It turns any statement (PDF, Excel, CSV, text) into a sequence of cells,
finds the cells whose text starts with a known label (config/vocabulary.yaml, English and German), and reads
the value from the rest of that cell or the cells after it. Numbers are read in the document's own convention
(1,234.56 or 1.234,56), amounts are scaled when the document says they are in thousands, and dates are read in
whichever of the usual formats they come in.

A statement that cannot be read, or reads but breaks the contract (config/contracts/gp_statement.yaml), never
reaches the warehouse: it goes to quarantine with the rule it broke.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..config import target_funds, vocabulary

AMOUNT_FIELDS = ("commitment", "paid_in", "distributed", "nav", "unfunded")
DATE_FIELDS = ("period_end", "statement_date")
MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [
            ("january", "jan", "januar", "jänner"),
            ("february", "feb", "februar"),
            ("march", "mar", "märz", "maerz"),
            ("april", "apr"),
            ("may", "mai"),
            ("june", "jun", "juni"),
            ("july", "jul", "juli"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct", "oktober", "okt"),
            ("november", "nov"),
            ("december", "dec", "dezember", "dez"),
        ]
    )
    for m in names
}
GERMAN_HINTS = (
    "stichtag",
    "zeichnungsbetrag",
    "eingezahlt",
    "ausschüttung",
    "währung",
    "anleger",
    "kapitalkonto",
    "erstellt am",
)


class ParseError(Exception):
    def __init__(self, rule: str, detail: str):
        super().__init__(f"{rule}: {detail}")
        self.rule = rule
        self.detail = detail


@dataclass
class Statement:
    fund: str | None = None
    period_end: dt.date | None = None
    statement_date: dt.date | None = None
    currency: str | None = None
    commitment: Decimal | None = None
    paid_in: Decimal | None = None
    distributed: Decimal | None = None
    nav: Decimal | None = None
    unfunded: Decimal | None = None
    unit_scale: int = 1
    parser: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            k: getattr(self, k)
            for k in ("fund", "period_end", "statement_date", "currency", *AMOUNT_FIELDS, "unit_scale")
        }


# --------------------------------------------------------------------------- cells from documents


def cells_from_file(path: Path) -> tuple[list[str], str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_cells(path), "pdf"
    if suffix in (".xlsx", ".xlsm"):
        return _xlsx_cells(path), "xlsx"
    if suffix == ".csv":
        return _csv_cells(path.read_text(encoding="utf-8-sig")), "csv"
    if suffix in (".txt", ".md"):
        return _text_cells(path.read_text(encoding="utf-8")), "text"
    raise ParseError("unsupported_format", f"{path.suffix} is not a statement format the platform reads")


def _pdf_cells(path: Path) -> list[str]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:  # a damaged PDF is a quarantine reason, not a crash
        raise ParseError("unreadable_pdf", str(e)[:200]) from e
    if not text.strip():
        raise ParseError("no_text_layer", "the PDF has no text layer (a scan); ask the manager for the original")
    return _text_cells(text)


def _text_cells(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        line = line.strip().strip("|").strip()
        if not line or set(line) <= set("-=|:*_ "):
            continue
        # table rows in text or Markdown ("| Label | Value |"), tab or wide-space columns, dot leaders
        parts = [p.strip(" *") for p in re.split(r"\s*\|\s*|\t|\s{3,}|\s*\.{3,}\s*|\s*…+\s*|\s+·\s+", line) if p.strip(" *")]
        for part in parts or [line]:
            out.extend(_split_label_value(part))
    return out


def _split_label_value(cell: str) -> list[str]:
    """'Commitment: 1,000.00' -> ['Commitment', '1,000.00']; a cell that is only a label or a value stays one."""
    m = re.match(r"^([^:\d]*[A-Za-zÄÖÜäöüß)\]])\s*:\s*(.+)$", cell)
    if m and re.search(r"\d", m.group(2)):
        return [m.group(1).strip(), m.group(2).strip()]
    m = re.match(r"^(.*?[A-Za-zÄÖÜäöüß)\]])\s+((?:[-(]?\s*(?:[A-Z]{3}|[€$£])\s*)?[-(]?\d[\d.,' ]*\)?(?:\s*(?:[A-Z]{3,4}|[€$£]))?)$", cell)
    if m and not _looks_like_date(m.group(2)) and not YEAR.fullmatch(m.group(2).strip()):
        return [m.group(1).strip(), m.group(2).strip()]
    return [cell]


YEAR = re.compile(r"(19|20)\d{2}")
UNIT_TOKEN = re.compile(r"(?i)^(?:[A-Z]{3}|[€$£]|teur|tusd|mio\.?|in tsd\.?|k|m|'000|000s)$")


def _xlsx_cells(path: Path) -> list[str]:
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True, read_only=True)
    out: list[str] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for v in row:
                if v is None or (isinstance(v, str) and not v.strip()):
                    continue
                if isinstance(v, dt.datetime):
                    out.append(v.date().isoformat())
                elif isinstance(v, dt.date):
                    out.append(v.isoformat())
                elif isinstance(v, float | int) and not isinstance(v, bool):
                    # six decimals, so a German reading never mistakes 123.456 for a thousands separator
                    out.append(f"{v:.6f}")
                else:
                    out.append(str(v).strip())
    return out


def _csv_cells(text: str) -> list[str]:
    sample = text[:2048]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ";" if sample.count(";") > sample.count(",") else ","
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ParseError("empty_csv", "a header and at least one row are needed")
    header = rows[0]
    known = sum(1 for h in header if classify(h) is not None)
    if known >= 3:  # a wide export: one column per field, one row per statement
        if len(rows) > 2:
            raise ParseError("several_statements", f"{len(rows) - 1} statements in one file: one per file is expected")
        out: list[str] = []
        for h, v in zip(header, rows[1], strict=False):
            out.extend([h.strip(), v.strip()])
        return out
    # a long export: one row per field (label, value, maybe a unit)
    return [c.strip() for r in rows for c in r if c.strip()]


# --------------------------------------------------------------------------- reading values


def _norm(s: str) -> str:
    s = s.lower().replace("_", " ").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip(" :.\t")


def _norm_label(s: str) -> str:
    s = s.lower().replace("_", " ").replace("’", " ").replace("'", " ").replace("-", " ").replace("/", " ")
    s = re.sub(r"[^\wäöüß ]+", " ", s)
    return " " + re.sub(r"\s+", " ", s).strip() + " "


def _has(text: str, words: list[str]) -> str | None:
    """The longest of `words` found in `text` as whole words."""
    best = None
    for w in words:
        n = _norm_label(w)
        if n in text and (best is None or len(n) > len(best)):
            best = n
    return best


@dataclass
class Label:
    field: str
    strength: int  # length of the matched word: "capital account balance" beats "capital account"
    marker: str  # cumulative | period | closing | opening | plain


AMOUNT_ORDER = ("unfunded", "commitment", "paid_in", "distributed", "nav")


def classify(cell: str) -> Label | None:
    """The field a label names, if any, and whether it is the cumulative, period, closing or opening figure."""
    if not re.search(r"[A-Za-zÄÖÜäöü]{2}", cell) or len(cell) > 70 or re.search(r"[a-z]\. [A-Z]", cell):
        return None  # prose, not a label
    text = _norm_label(re.sub(r"\d{1,4}[./-]\d{1,2}[./-]\d{2,4}", " ", cell))
    voc = vocabulary()
    marks = voc["markers"]

    def marker() -> str:
        for m in ("opening", "closing", "period", "cumulative"):
            if _has(text, marks[m]):
                return m
        return "plain"

    for name in AMOUNT_ORDER:
        f = voc["fields"][name]
        hit = _has(text, f["words"])
        if hit and not _has(text, f.get("not", [])):
            return Label(name, len(hit), marker())
    for name in ("statement_date", "period_end", "currency", "fund"):
        hit = _has(text, voc["fields"][name]["words"])
        if hit:
            return Label(name, len(hit), "plain")
    return None


def _looks_like_date(raw: str) -> bool:
    return parse_date(raw) is not None and not re.fullmatch(r"[-(]?[\d.,' ]+\)?", raw.strip()) or bool(
        re.fullmatch(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}-\d{2}-\d{2}", raw.strip())
    )


def _is_number_cell(raw: str) -> bool:
    s = re.sub(r"(?i)\b(eur|usd|gbp|chf|teur|tusd|mio|m|k)\b|[€$£\s]", "", raw.strip())
    return (
        bool(re.fullmatch(r"[-(]?\d[\d.,']*\)?-?", s))
        and not _looks_like_date(raw)
        and "%" not in raw
        and not YEAR.fullmatch(raw.strip())  # a year on its own is not an amount
    )


def parse_number(raw: str, german: bool) -> Decimal | None:
    """A number written either way: 1,234,567.89 or 1.234.567,89, with currency signs, spaces or parentheses."""
    s = raw.strip()
    neg = (s.startswith("(") and s.endswith(")")) or s.startswith("-") or s.endswith("-")
    s = re.sub(r"[^\d.,]", "", s.replace("'", ""))
    if not re.search(r"\d", s):
        return None
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
    elif "," in s:
        dec = "" if not german and re.fullmatch(r"\d{1,3}(,\d{3})+", s) else ","
    elif "." in s:
        dec = "" if (german and re.fullmatch(r"\d{1,3}(\.\d{3})+", s)) or s.count(".") > 1 else "."
    else:
        dec = ""
    thousands = {",": ".", ".": ",", "": ",."}[dec]
    for ch in thousands:
        s = s.replace(ch, "")
    s = s.replace(",", ".")
    try:
        v = Decimal(s)
    except InvalidOperation:
        return None
    return -v if neg else v


DATE_PATTERNS = [
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), "iso"),
    (re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})"), "dmy_dot"),
    (re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})"), "slash"),
    (re.compile(r"([A-Za-zÄÖÜäöü]+)\.? (\d{1,2}),? (\d{4})"), "mdy_words"),
    (re.compile(r"(\d{1,2})\.? ([A-Za-zÄÖÜäöü]+)\.? (\d{4})"), "dmy_words"),
]


def parse_date(raw: str, prefer_us: bool | None = None) -> dt.date | None:
    for rx, kind in DATE_PATTERNS:
        m = rx.search(raw)
        if not m:
            continue
        try:
            if kind == "iso":
                return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if kind == "dmy_dot":
                return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if kind == "slash":
                a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if a > 12:
                    return dt.date(y, b, a)
                if b > 12:
                    return dt.date(y, a, b)
                return dt.date(y, a, b) if prefer_us else dt.date(y, b, a)
            if kind == "mdy_words":
                mon = MONTHS.get(m.group(1).lower())
                if mon:
                    return dt.date(int(m.group(3)), mon, int(m.group(2)))
            if kind == "dmy_words":
                mon = MONTHS.get(m.group(2).lower())
                if mon:
                    return dt.date(int(m.group(3)), mon, int(m.group(1)))
        except ValueError:
            continue
    return None


def _unit_scale(text: str) -> int:
    t = " " + _norm(text) + " "
    units = vocabulary()["units"]
    if any(re.search(r"(?<![a-z])" + re.escape(_norm(u)) + r"(?![a-z])", t) for u in units["millions"]):
        return 1_000_000
    if any(re.search(r"(?<![a-z])" + re.escape(_norm(u)) + r"(?![a-z])", t) for u in units["thousands"]):
        return 1000
    return 1


def _currency(text: str) -> str | None:
    up = text.upper()
    for cur in vocabulary()["currencies"]:
        if re.search(rf"(?<![A-Z]){cur}(?![A-Z])", up) or re.search(rf"(?<![A-Z])T{cur}(?![A-Z])", up):
            return cur
    if "€" in text:
        return "EUR"
    if "$" in text:
        return "USD"
    return None


def identify_fund(cells: list[str], stated: str | None) -> str | None:
    """The target fund a statement is about: by its name (without legal suffixes) anywhere in the document."""
    text = _norm(" ".join(cells))
    best = None
    for fid, f in target_funds().items():
        name = _norm(f["name"])
        if name in text or (stated and _norm(stated).startswith(name)):
            if best is None or len(name) > len(_norm(target_funds()[best]["name"])):
                best = fid
        elif re.search(rf"(?<![a-z0-9]){fid.lower()}(?![a-z0-9])", text):
            best = best or fid
    return best


@dataclass
class Candidate:
    field: str
    marker: str
    strength: int
    raw: str
    position: int
    label_date: dt.date | None = None


RANK = {"cumulative": 0, "closing": 0, "plain": 1, "period": 9, "opening": 9}
PERIOD_PHRASES = re.compile(
    r"(?i)(?:quarter|period|year|halbjahr|quartal)\s+(?:ended|ending|end|endend)\s+(?:on\s+)?(.{6,24}?\d{4})"
    r"|\bas\s+(?:of|at)\s+(.{6,24}?\d{4})|\bzum\s+(\d{1,2}\.\s?\d{1,2}\.\s?\d{4}|\d{1,2}\.?\s+\w+\s+\d{4})"
    r"|\bper\s+(\d{1,2}\.\d{1,2}\.\d{4})|\bto\s+(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},\s+\d{4})"
    r"|(?:statement|report|auszug|bericht)\s*[-–:]\s*(\d{1,2}\.?\s?\w+\.?\s?\d{4}|\w+\s+\d{1,2},\s+\d{4})"
)


def parse_cells(cells: list[str], parser: str) -> Statement:
    st = Statement(parser=parser)
    doc = " ".join(cells)
    german = sum(h in doc.lower() for h in GERMAN_HINTS) >= 2 or bool(re.search(r"\d\.\d{3},\d{2}", doc))
    us_dates = bool(re.search(r"\b(0?[1-9]|1[0-2])/(29|30|31)/\d{4}\b", doc))
    found: list[Candidate] = []
    labels = [classify(c) for c in cells]
    period_words = vocabulary()["fields"]["period_end"]["words"]
    for i, (cell, lab) in enumerate(zip(cells, labels, strict=True)):
        label_date = parse_date(cell, us_dates)
        # "Net asset value as at 30 September 2026", "Zwischenmitteilung - Stichtag 15.05.2026": a period end,
        # whatever else the cell names
        if label_date and len(cell) <= 90:
            hit = _has(_norm_label(cell), period_words)
            if hit and (lab is None or lab.field != "period_end"):
                found.append(Candidate("period_end", "plain", len(hit), cell, i))
        if lab is None:
            continue
        if lab.field in DATE_FIELDS and label_date:  # "Kapitalkontoauszug zum 30.06.2026": the date is in the label
            found.append(Candidate(lab.field, lab.marker, lab.strength, cell, i))
            continue
        # the value: in the following cells, before the next label
        for k in range(i + 1, min(i + 4, len(cells))):
            nxt = cells[k]
            if labels[k] is not None and not _is_number_cell(nxt):
                break
            if lab.field in AMOUNT_FIELDS and not _is_number_cell(nxt) and not UNIT_TOKEN.match(nxt.strip()) and nxt.strip() not in ("-", "–"):
                break  # another row's text: this label has no value of its own (a heading)
            if lab.field in AMOUNT_FIELDS and _is_number_cell(nxt):
                # a period column and a cumulative column: the cumulative one is on the right
                run = [nxt]
                while k + len(run) < len(cells) and len(run) < 3 and _is_number_cell(cells[k + len(run)]):
                    run.append(cells[k + len(run)])
                found.append(Candidate(lab.field, lab.marker, lab.strength, run[-1], i, label_date))
                break
            if lab.field in DATE_FIELDS and parse_date(nxt, us_dates):
                found.append(Candidate(lab.field, lab.marker, lab.strength, nxt, i))
                break
            if lab.field == "currency" and _currency(nxt):
                found.append(Candidate("currency", "plain", lab.strength, nxt, i))
                break
            if lab.field == "fund" and nxt and not _is_number_cell(nxt):
                found.append(Candidate("fund", "plain", lab.strength, nxt, i))
                break
        else:
            if lab.field in DATE_FIELDS and label_date:  # "Kapitalkontoauszug zum 30.06.2026"
                found.append(Candidate(lab.field, lab.marker, lab.strength, cell, i))
            if lab.field == "currency" and _currency(cell):  # "All amounts in USD"
                found.append(Candidate("currency", "plain", lab.strength, cell, i))

    st.unit_scale = _unit_scale(doc)
    # dates first: the closing NAV is the one at the period end
    dates = {}
    for name in DATE_FIELDS:
        cands = [c for c in found if c.field == name]
        if cands:
            best = max(cands, key=lambda c: (c.strength, -c.position))
            all_dates = [d for d in (_all_dates(best.raw, us_dates)) if d]
            if all_dates:
                dates[name] = max(all_dates) if name == "period_end" else all_dates[0]
    if "period_end" not in dates:
        for m in PERIOD_PHRASES.finditer(doc):
            d = parse_date(next(g for g in m.groups() if g), us_dates)
            if d and _is_quarter_end(d):
                dates["period_end"] = d
                break
    st.period_end = dates.get("period_end")
    st.statement_date = dates.get("statement_date")

    for name in AMOUNT_FIELDS:
        cands = [c for c in found if c.field == name and RANK[c.marker] < 9]
        if name == "nav" and st.period_end:
            # a roll-forward: "capital at 31 March 2026" is the closing NAV, "at 31 December 2025" the opening
            dated = [c for c in cands if c.label_date is not None]
            if dated:
                cands = [c for c in dated if c.label_date == st.period_end] or [c for c in cands if c.label_date is None]
        if not cands:
            continue
        best = min(cands, key=lambda c: (RANK[c.marker], -c.strength, c.position))
        v = parse_number(best.raw, german)
        if v is None:
            continue
        v = abs(v) if name == "distributed" else v  # some managers show money out as negative
        setattr(st, name, (v * st.unit_scale).quantize(Decimal("0.01")))

    cur = next((c for c in found if c.field == "currency"), None)
    st.currency = _currency(cur.raw) if cur else None
    st.currency = st.currency or _currency(" ".join(c.raw for c in found if c.field in AMOUNT_FIELDS)) or _currency_words(doc)
    stated_fund = next((c.raw for c in found if c.field == "fund"), None)
    st.fund = identify_fund(cells, stated_fund)
    if st.currency is None and st.fund:
        st.currency = target_funds()[st.fund]["currency"]
        st.notes.append("currency taken from the fund's master data: the statement does not state it")
    if st.unit_scale != 1:
        st.notes.append(f"amounts scaled by {st.unit_scale}: the statement says so")
    if (
        None not in (st.commitment, st.paid_in, st.unfunded)
        and abs(st.commitment - st.paid_in - st.unfunded) > st.commitment * Decimal("0.005")  # type: ignore[operator]
    ):
        # recallable distributions and fees outside the commitment make this legitimate: noted, not rejected
        st.notes.append(f"unfunded {st.unfunded} is not commitment minus paid-in")
    return st


def _all_dates(raw: str, us: bool) -> list[dt.date]:
    out = []
    for part in re.split(r"\s+(?:to|bis|until|-|–)\s+", raw):
        d = parse_date(part, us)
        if d:
            out.append(d)
    return out


def _currency_words(doc: str) -> str | None:
    text = _norm_label(doc)
    for cur, words in vocabulary()["currency_words"].items():
        if cur != "EUR" and _has(text, words):
            return cur
    return "EUR" if _has(text, vocabulary()["currency_words"]["EUR"]) else None


def parse_statement(path: Path) -> Statement:
    cells, kind = cells_from_file(path)
    return parse_cells(cells, kind)


# --------------------------------------------------------------------------- contract


def _is_quarter_end(d: dt.date) -> bool:
    return d.month in (3, 6, 9, 12) and (d + dt.timedelta(days=1)).day == 1


def violations(st: Statement) -> list[tuple[str, str]]:
    """Rules of config/contracts/gp_statement.yaml the statement breaks, as (rule, detail)."""
    out: list[tuple[str, str]] = []
    missing = [
        f
        for f in ("fund", "period_end", "currency", "commitment", "paid_in", "distributed", "nav")
        if getattr(st, f) is None
    ]
    if missing:
        out.append(("required_fields", "missing: " + ", ".join(missing)))
        return out
    assert st.period_end and st.currency and st.commitment is not None and st.paid_in is not None
    assert st.distributed is not None and st.nav is not None
    if st.currency not in vocabulary()["currencies"]:
        out.append(("currency_known", st.currency))
    if not _is_quarter_end(st.period_end):
        out.append(("quarter_end", f"{st.period_end} is not the last day of a quarter"))
    if min(st.commitment, st.paid_in, st.distributed, st.nav) < 0:
        out.append(("amounts_not_negative", "an amount is negative"))
    if st.paid_in > st.commitment * Decimal("1.02"):
        out.append(("paid_in_within_commitment", f"paid in {st.paid_in} against a commitment of {st.commitment}"))
    if st.statement_date is not None and st.statement_date < st.period_end:
        out.append(("statement_after_period", f"issued {st.statement_date} before the period end {st.period_end}"))
    return out
